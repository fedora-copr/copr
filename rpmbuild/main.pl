#!/usr/bin/perl

use strict;
use warnings;

use Getopt::Long::Descriptive;
use Data::Dumper;
use Data::Types qw(:all);
use Config::IniFiles;
use Text::Template::Simple;
use JSON::Tiny qw(decode_json);
use IPC::System::Simple qw(system capture);
use HTTP::Tiny;
use File::Path qw(make_path remove_tree);
use File::Copy;
use File::Temp;
use File::Basename;
use Cwd;
use IPC::Run qw(run);
use Time::Out qw(timeout);
use File::Tee qw(tee);
use Fcntl qw(:DEFAULT :flock);
use Proc::Fork;
use POSIX;
use URI;

# Parse arguments
my ($opt, $usage) = describe_options(
    '%c %o <task_id>',
    [ 'detached|d', "run in background" ],
    [ 'verbose|v', "print debugging information" ],
    [ 'help|h', "print usage message and exit", { shortcircuit => 1 } ],
);

if ($opt->help or @ARGV != 1) {
    print("Runs COPR build of the specified task ID, e.g. 551347-epel-7-x86_64,
           and puts results into /var/lib/copr-rpmbuild/results/.\n\n");
    print($usage->text);
    exit;
}

# Get task ID
my $task_id = $ARGV[0];

# allow only one instance
my $lockfile = "/var/lib/copr-rpmbuild/lockfile";
open(my $lockfile_fh, ">", $lockfile) or die "Can't open lockfile: $!";
flock($lockfile_fh, LOCK_EX | LOCK_NB) or die "Only one instance allowed: $!";

# Init
my $resultdir = '/var/lib/copr-rpmbuild/results';
remove_tree( $resultdir, {keep_root => 1} );

my $logfile = '/var/lib/copr-rpmbuild/main.log';

if ($opt->detached) {
    # One-stop shopping: fork, die on error, parent process exits.
    run_fork { parent { my $child_pid = shift; print $child_pid; exit } };

    # Other daemon initialization activities.
    POSIX::setsid() or die "Cannot start a new session: $!\n";
    close $_ for *STDIN, *STDOUT, *STDERR;
    open(my $logfile_fh, '>', $logfile);
    open(STDOUT, '>&', $logfile_fh);
    open(STDERR, '>&', \*STDOUT);
} else {
    tee(STDOUT, '>>', $logfile);
    tee(STDERR, '>>', $logfile);
}

my $pidfile = '/var/lib/copr-rpmbuild/pid';
open(my $pidfile_fh, ">", $pidfile) or die "Can't open pidfile: $!";
print $pidfile_fh $$;

my $cfg = Config::IniFiles->new( -file => "/etc/copr-rpmbuild/main.ini" ) or die;

# Get task from frontend
my $response = HTTP::Tiny->new->get(
    URI->new_abs('/backend/get-build-task/'.$task_id, $cfg->val('main', 'frontend_url'))
);
if (!$response->{success} or !$response->{content}) {
    print "$response->{status} $response->{reason}\n";
    print "$response->{content}\n";
    die "Failed to get build of the specified ID!\n";
}

# Parse it
my $task = decode_json $response->{content};

if ($opt->verbose) {
    print "> Received build task:\n\n";
    print Data::Dumper->Dump([$task], [qw(task)]);
    print "\n";
}

# Generate mock config
my $tts = Text::Template::Simple->new();
my $mock_config = $tts->compile(
    '/etc/copr-rpmbuild/mockcfg.tmpl',
    [
    chroot => $task->{chroot},
    task_id => $task->{task_id},
    buildroot_pkgs => $task->{buildroot_pkgs},
    repos => $task->{repos},
    enable_net => $task->{enable_net},
    use_bootstrap_container => $task->{use_bootstrap_container}
    ]
);

# Copy all the mock configuration to the target configs directory
my $configs_dir = $resultdir.'/configs';
make_path($configs_dir);
copy("/etc/mock/site-defaults.cfg", $configs_dir) or die "Copy of site-defaults.cfg failed: $!";
copy("/etc/mock/$task->{chroot}.cfg", $configs_dir) or die "Copy $task->{chroot}.cfg failed: $!";
open(my $child_fh, ">", $configs_dir."/child.cfg") or die "Can't open > child.cfg: $!";
print $child_fh $mock_config;

# Get sources from dist-git
my $origdir = getcwd;
my $workdir = File::Temp->newdir();
chdir $workdir;

my $distgit_clone_url = $cfg->val('main', 'distgit_clone_url');
$distgit_clone_url =~ s/^(.*)\/$/$1/;
print capture("git", "clone", "$distgit_clone_url/$task->{git_repo}.git");
my $pkgname = basename $task->{git_repo};
chdir $pkgname;
print capture("git", "checkout", "$task->{git_hash}");
open(my $sources_fh, "<", "sources") or die "Can't find 'sources' file: $!";
my @sources = <$sources_fh>;

my $lookasideurl = $cfg->val('main', 'distgit_lookaside_url');
$lookasideurl =~ s/^(.*)\/$/$1/;

foreach my $source (@sources) {
    my ($hashtype, $tarball, $hashval);
    if ($source =~ /^(\S+)\s*(\S+)$/) { # old sources format
        # 33b5dd0543a5e02df22ac6b8c00538a5  example-1.0.4.tar.gz
        ($hashval, $tarball) = ($1, $2);
        system("curl", "-L",
                "-H", "Pragma:",
                "-o", "$tarball",
                "-R",
                "-S",
                "--fail",
                "--retry", "5",
                "--max-time", "15",
                "$lookasideurl/$task->{git_repo}/$tarball/$hashval/$tarball");

        my $tmp = File::Temp->new();
        print $tmp $source;
        close $tmp;
        system("md5sum", "-c", $tmp) and die "Tarball $tarball not present or invalid checksum: $!";
    } elsif ($source =~ /^(\S+)\s*\((\S+)\)\s*=\s*(\S+)$/) { # new sources format 
        # SHA512 (dist-git-1.2.tar.gz) = 0850e6955f875b942ca4e2802b750b2d4ccc349a51deae97fb0cfe21c41f5b01dfce4c1cf3fcd56c16062d57b0ccb75e3fa2f901c98a843bc3bf14141f427a03
        ($hashtype, $tarball, $hashval) = (lc $1, $2, $3);
        system("curl", "-L",
                "-H", "Pragma:",
                "-o", "$tarball",
                "-R",
                "-S",
                "--fail",
                "--retry", "5",
                "--max-time", "15",
                "$lookasideurl/$task->{git_repo}/$tarball/$hashtype/$hashval/$tarball");

        my $tmp = File::Temp->new();
        print $tmp $source;
        close $tmp;
        system($hashtype."sum", "-c", $tmp) and die "Tarball $tarball not present or invalid checksum: $!";
    } else {
        die "Unexpected format of sources file!";
    }
}

my $timeout = ($task->{timeout} or 1e6);

# Do the build
timeout $timeout => sub {

    # Build srpm
    run [
        "unbuffer", "/usr/bin/mock",
        "--buildsrpm",
        "--spec", "$pkgname.spec",
        "--sources", ".",
        "--resultdir", "intermediate-srpm",
        "--no-cleanup-after",
        "--configdir", "$configs_dir",
        "-r", "child",
    ] or die "Could not build srpm: $!";

    my @srpm = glob "intermediate-srpm/*.src.rpm";

    # Build rpm
    run [
        "unbuffer", "/usr/bin/mock",
        "--rebuild", $srpm[0],
        "--configdir", "$configs_dir",
        "--resultdir", "$resultdir",
        "--no-clean",
        "-r", "child",
    ] or die "Could not build rpm: $!";

};

chdir $origdir;

# Generate success file
open(my $success_fh, ">", $resultdir."/success") or die "Can't create success file: $!";
print $success_fh "done";
