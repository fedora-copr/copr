#!/usr/bin/python -tt
# by skvidal
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA 02110-1301  USA.
# copyright 2012 Red Hat, Inc.


# take list of pkgs
# take single hostname
# send 1 pkg at a time to host
# build in remote w/mockchain
# rsync results back
# repeat
# take args from mockchain (more or less)


import os
import sys
import subprocess

import ansible.runner
import optparse
from operator import methodcaller
import pipes
import time
import socket
import traceback

# where we should execute mockchain from on the remote
mockchain = '/usr/bin/mockchain'
# rsync path
rsync = '/usr/bin/rsync'

DEF_REMOTE_BASEDIR = '/var/tmp'
DEF_TIMEOUT = 3600
DEF_REPOS = []
DEF_CHROOT = None
DEF_USER = 'mockbuilder'
DEF_DESTDIR = os.getcwd()
DEF_MACROS = {}
DEF_BUILDROOT_PKGS = ''

class SortedOptParser(optparse.OptionParser):
    '''Optparser which sorts the options by opt before outputting --help'''
    def format_help(self, formatter=None):
        self.option_list.sort(key=methodcaller('get_opt_string'))
        return optparse.OptionParser.format_help(self, formatter=None)


def createrepo(path):
    if os.path.exists(path + '/repodata/repomd.xml'):
        comm = ['/usr/bin/createrepo', '--database', '--update', path]
    else:
        comm = ['/usr/bin/createrepo', '--database', path]
    cmd = subprocess.Popen(comm,
             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = cmd.communicate()
    return cmd.returncode, out, err

def read_list_from_file(fn):
    lst = []
    f = open(fn, 'r')
    for line in f.readlines():
        line = line.replace('\n','')
        line = line.strip()
        if line.startswith('#'):
            continue
        lst.append(line)

    return lst

def log(lf, msg):
    if lf:
        now = time.time()
        try:
            open(lf, 'a').write(str(now) + ':' + msg + '\n')
        except (IOError, OSError), e:
            sys.stderr.write('Could not write to logfile %s - %s\n' % (lf, str(e)))
    print msg

def get_ans_results(results, hostname):
    if hostname in results['dark']:
        return results['dark'][hostname]
    if hostname in results['contacted']:
        return results['contacted'][hostname]

    return {}

def _create_ans_conn(hostname, username, timeout):
    ans_conn = ansible.runner.Runner(remote_user=username,
          host_list=hostname + ',', pattern=hostname, forks=1, transport='ssh',
          timeout=timeout)
    return ans_conn

def check_for_ans_error(results, hostname, err_codes=[], success_codes=[0],
                             return_on_error=['stdout', 'stderr']):
    """ returns True or False + dict
    dict includes 'msg'
    may include 'rc', 'stderr', 'stdout' and any other
    requested result codes
    """
    err_results = {}

    if 'dark' in results and hostname in results['dark']:
        err_results['msg'] = "Error: Could not contact/connect to %s." % hostname
        return (True, err_results)

    error = False

    if err_codes or success_codes:
        if hostname in results['contacted']:
            if 'rc' in results['contacted'][hostname]:
                rc = int(results['contacted'][hostname]['rc'])
                err_results['rc'] = rc
                # check for err codes first
                if rc in err_codes:
                    error = True
                    err_results['msg'] = 'rc %s matched err_codes' % rc
                elif rc not in success_codes:
                    error = True
                    err_results['msg'] = 'rc %s not in success_codes' % rc
            elif 'failed' in results['contacted'][hostname] and results['contacted'][hostname]['failed']:
                error = True
                err_results['msg'] = 'results included failed as true'

        if error:
            for item in return_on_error:
                if item in results['contacted'][hostname]:
                    err_results[item] = results['contacted'][hostname][item]

    return error, err_results


class MockRemoteError(Exception):

    def __init__(self, msg):
        super(MockRemoteError, self).__init__()
        self.msg = msg

    def __str__(self):
        return self.msg

class BuilderError(MockRemoteError):
    pass

class DefaultCallBack(object):
    def __init__(self, **kwargs):
        self.quiet = kwargs.get('quiet', False)
        self.logfn = kwargs.get('logfn', None)

    def start_build(self, pkg):
        pass

    def end_build(self, pkg):
        pass

    def start_download(self, pkg):
        pass

    def end_download(self, pkg):
        pass

    def error(self, msg):
        self.log("Error: %s" % msg)

    def log(self, msg):
        if not self.quiet:
            print msg

class CliLogCallBack(DefaultCallBack):
    def __init__(self, **kwargs):
        DefaultCallBack.__init__(self, **kwargs)

    def start_build(self, pkg):
        msg = "Start build: %s" % pkg
        self.log(msg)


    def end_build(self, pkg):
        msg = "End Build: %s" % pkg
        self.log(msg)

    def start_download(self, pkg):
        msg = "Start retrieve results for: %s" % pkg
        self.log(msg)

    def end_download(self, pkg):
        msg = "End retrieve results for: %s" % pkg
        self.log(msg)

    def error(self, msg):
        self.log("Error: %s" % msg)

    def log(self, msg):
        if self.logfn:
            now = time.time()
            try:
                open(self.logfn, 'a').write(str(now) + ':' + msg + '\n')
            except (IOError, OSError), e:
                print >> sys.stderr, 'Could not write to logfile %s - %s' % (self.logfn, str(e))
        if not self.quiet:
            print msg

class Builder(object):
    def __init__(self, hostname, username, timeout, mockremote, buildroot_pkgs):
        self.hostname = hostname
        self.username = username
        self.timeout = timeout
        self.chroot = mockremote.chroot
        self.repos = mockremote.repos
        self.mockremote = mockremote
        if buildroot_pkgs is None:
            self.buildroot_pkgs = ''
        else:
            self.buildroot_pkgs = buildroot_pkgs
        self.checked = False
        self._tempdir = None
        # if we're at this point we've connected and done stuff on the host
        self.conn = _create_ans_conn(self.hostname, self.username, self.timeout)
        self.root_conn = _create_ans_conn(self.hostname, 'root', self.timeout)
        # check out the host - make sure it can build/be contacted/etc
        self.check()

    @property
    def remote_build_dir(self):
        return self.tempdir + '/build/'

    @property
    def tempdir(self):
        if self.mockremote.remote_tempdir:
            return self.mockremote.remote_tempdir

        if self._tempdir:
            return self._tempdir

        cmd = '/bin/mktemp -d %s/%s-XXXXX' % (self.mockremote.remote_basedir, 'mockremote')
        self.conn.module_name = "shell"
        self.conn.module_args = str(cmd)
        results = self.conn.run()
        tempdir = None
        for hn, resdict in results['contacted'].items():
            tempdir = resdict['stdout']

        # if still nothing then we've broken
        if not tempdir:
            raise BuilderError('Could not make tmpdir on %s' % self.hostname)

        cmd = "/bin/chmod 755 %s" % tempdir
        self.conn.module_args = str(cmd)
        self.conn.run()
        self._tempdir = tempdir

        return self._tempdir

    @tempdir.setter
    def tempdir(self, value):
        self._tempdir = value

    def _get_remote_pkg_dir(self, pkg):
        # the pkg will build into a dir by mockchain named:
        # $tempdir/build/results/$chroot/$packagename
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace('.src.rpm', '')
        remote_pkg_dir = os.path.normpath(self.remote_build_dir + '/results/' + self.chroot + '/' + pdn)
        return remote_pkg_dir

    def modify_base_buildroot(self):
        """ modify mock config for current chroot

        packages in buildroot_pkgs are added to minimal buildroot """
        if "'%s '" % self.buildroot_pkgs != pipes.quote(str(self.buildroot_pkgs)+' '):
            # just different test if it contains only alphanumeric characters allowed in packages name
            raise BuilderError("Do not try this kind of attack on me")
        self.root_conn.module_name = "lineinfile"
        self.root_conn.module_args = """dest=/etc/mock/%s.cfg line="config_opts['chroot_setup_cmd'] = 'install @buildsys-build %s'" regexp="^.*chroot_setup_cmd.*$" """ % (self.chroot, self.buildroot_pkgs)
        self.mockremote.callback.log('putting %s into minimal buildroot of %s' % (self.buildroot_pkgs, self.chroot))
        results = self.root_conn.run()

        is_err, err_results = check_for_ans_error(results, self.hostname, success_codes=[0],
                          return_on_error=['stdout', 'stderr'])
        if is_err:
            self.mockremote.callback.log("Error: %s" % err_results)
            myresults = get_ans_results(results, self.hostname)
            self.mockremote.callback.log("%s" % myresults)


    def build(self, pkg):

        # build the pkg passed in
        # add pkg to various lists
        # check for success/failure of build
        # return success/failure,stdout,stderr of build command
        # returns success_bool, out, err

        success = False
        self.modify_base_buildroot()

        # check if pkg is local or http
        dest = None
        if os.path.exists(pkg):
            dest = os.path.normpath(self.tempdir + '/' + os.path.basename(pkg))
            self.conn.module_name = "copy"
            margs = 'src=%s dest=%s' % (pkg, dest)
            self.conn.module_args = str(margs)
            self.mockremote.callback.log("Sending %s to %s to build" % (os.path.basename(pkg), self.hostname))

            # FIXME should probably check this but <shrug>
            self.conn.run()
        else:
            dest = pkg

        # construct the mockchain command
        buildcmd = "%s -r %s -l %s " % (mockchain, pipes.quote(self.chroot), pipes.quote(self.remote_build_dir))
        for r in self.repos:
            buildcmd += "-a %s " % pipes.quote(r)

        if self.mockremote.macros:
            for k, v in self.mockremote.macros.items():
                mock_opt = '--define=%s %s' % (k, v)
                buildcmd += '-m %s ' % pipes.quote(mock_opt)

        buildcmd += dest

        #print '  Running %s on %s' % (buildcmd, hostname)
        # run the mockchain command async
        # this runs it sync - FIXME
        self.mockremote.callback.log('executing: %r' % buildcmd)
        self.conn.module_name = "shell"
        self.conn.module_args = str(buildcmd)
        results = self.conn.run()

        is_err, err_results = check_for_ans_error(results, self.hostname, success_codes=[0],
                          return_on_error=['stdout', 'stderr'])
        if is_err:
            return success, err_results.get('stdout', ''), err_results.get('stderr', '')

        # we know the command ended successfully but not if the pkg built successfully
        myresults = get_ans_results(results, self.hostname)
        out = myresults.get('stdout', '')
        err = myresults.get('stderr', '')

        successfile = self._get_remote_pkg_dir(pkg) + '/success'
        testcmd = '/usr/bin/test -f %s' % successfile
        self.conn.module_args = str(testcmd)
        results = self.conn.run()
        is_err, err_results = check_for_ans_error(results, self.hostname, success_codes=[0])
        if not is_err:
            success = True

        return success, out, err

    def download(self, pkg, destdir):
        # download the pkg to destdir using rsync + ssh
        # return success/failure, stdout, stderr

        success = False
        rpd = self._get_remote_pkg_dir(pkg)
        destdir = "'" + destdir.replace("'", "'\\''") + "'" # make spaces work w/our rsync command below :(
        # build rsync command line from the above
        remote_src = '%s@%s:%s' % (self.username, self.hostname, rpd)
        ssh_opts = "'ssh -o PasswordAuthentication=no -o StrictHostKeyChecking=no'"
        command = "%s -avH -e %s %s %s/" % (rsync, ssh_opts, remote_src, destdir)
        cmd = subprocess.Popen(command, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        # rsync results into opts.destdir
        out, err = cmd.communicate()
        if cmd.returncode:
            success = False
        else:
            success = True

        return success, out, err

    def check(self):
        # do check of host
        # set checked if successful
        # return success/failure, errorlist

        if self.checked:
            return True, []

        errors = []

        try:
            socket.gethostbyname(self.hostname)
        except socket.gaierror:
            raise BuilderError('%s could not be resolved' % self.hostname)

        self.conn.module_name = "shell"
        self.conn.module_args = str("/bin/rpm -q mock rsync")
        res = self.conn.run()
        # check for mock/rsync from results
        is_err, err_results = check_for_ans_error(res, self.hostname, success_codes=[0])
        if is_err:
            if 'rc' in err_results:
                errors.append('Warning: %s does not have mock or rsync installed' % self.hostname)
            else:
                errors.append(err_results['msg'])


        # test for path existence for mockchain and chroot config for this chroot
        self.conn.module_name = "shell"
        self.conn.module_args = "/usr/bin/test -f %s && /usr/bin/test -f /etc/mock/%s.cfg" % (mockchain, self.chroot)
        res = self.conn.run()

        is_err, err_results = check_for_ans_error(res, self.hostname, success_codes=[0])
        if is_err:
            if 'rc' in err_results:
                errors.append('Warning: %s lacks mockchain or the chroot %s' % (self.hostname, self.chroot))
            else:
                errors.append(err_results['msg'])

        if not errors:
            self.checked = True
        else:
            msg = '\n'.join(errors)
            raise BuilderError(msg)


class MockRemote(object):
    def __init__(self, builder=None, user=DEF_USER, timeout=DEF_TIMEOUT,
                 destdir=DEF_DESTDIR, chroot=DEF_CHROOT, cont=False, recurse=False,
                 repos=DEF_REPOS, callback=None,
                 remote_basedir=DEF_REMOTE_BASEDIR, remote_tempdir=None,
                 macros=DEF_MACROS,
                 buildroot_pkgs=DEF_BUILDROOT_PKGS):

        self.destdir = destdir
        self.chroot = chroot
        self.repos = repos
        self.cont = cont
        self.recurse = recurse
        self.callback = callback
        self.remote_basedir = remote_basedir
        self.remote_tempdir = remote_tempdir
        self.macros = macros

        if not self.callback:
            self.callback = DefaultCallBack()

        self.callback.log("Setting up builder: %s" % builder)
        self.builder = Builder(builder, user, timeout, self, buildroot_pkgs)

        if not self.chroot:
            raise MockRemoteError("No chroot specified!")


        self.failed = []
        self.finished = []
        self.pkg_list = []


    def _get_pkg_destpath(self, pkg):
        s_pkg = os.path.basename(pkg)
        pdn = s_pkg.replace('.src.rpm', '')
        resdir = '%s/%s/%s' % (self.destdir, self.chroot, pdn)
        resdir = os.path.normpath(resdir)
        return resdir

    def build_pkgs(self, pkgs=None):

        if not pkgs:
            pkgs = self.pkg_list

        built_pkgs = []
        downloaded_pkgs = {}

        try_again = True
        to_be_built = pkgs
        while try_again:
            self.failed = []
            just_built = []
            for pkg in to_be_built:
                if pkg in just_built:
                    self.callback.log("skipping duplicate pkg in this list: %s" % pkg)
                    continue
                else:
                    just_built.append(pkg)

                p_path = self._get_pkg_destpath(pkg)

                # check the destdir to see if these pkgs need to be built
                if os.path.exists(p_path):
                    if os.path.exists(p_path + '/success'):
                        self.callback.log("Skipping already built pkg %s" % os.path.basename(pkg))
                        continue
                    # if we're asking to build it and it is marked as fail - nuke
                    # the failure and try rebuilding it
                    elif os.path.exists(p_path + '/fail'):
                        os.unlink(p_path + '/fail')

                # off to the builder object
                # building
                self.callback.start_build(pkg)
                b_status, b_out, b_err = self.builder.build(pkg)
                self.callback.end_build(pkg)

                # downloading
                self.callback.start_download(pkg)
                # mockchain makes things with the chroot appended - so suck down
                # that pkg subdir from w/i that location
                chroot_dir = os.path.normpath(self.destdir + '/' + self.chroot)
                d_ret, d_out, d_err = self.builder.download(pkg, chroot_dir)
                if not d_ret:
                    msg = "Failure to download %s: %s" % (pkg, d_out + d_err)
                    if not self.cont:
                        raise MockRemoteError, msg
                    self.callback.error(msg)

                self.callback.end_download(pkg)
                # write out whatever came from the builder call into the destdir/chroot
                if not os.path.exists(chroot_dir):
                    os.makedirs(self.destdir + '/' + self.chroot)
                r_log = open(chroot_dir + '/mockchain.log', 'a')
                r_log.write('\n\n%s\n\n' % pkg)
                r_log.write(b_out)
                if b_err:
                    r_log.write('\nstderr\n')
                    r_log.write(b_err)
                r_log.close()


                # checking where to stick stuff
                if not b_status:
                    if self.recurse:
                        self.failed.append(pkg)
                        self.callback.error("Error building %s, will try again" % os.path.basename(pkg))
                    else:
                        msg = "Error building %s\nSee logs/resultsin %s" % (os.path.basename(pkg), self.destdir)
                        if not self.cont:
                            raise MockRemoteError, msg
                        self.callback.error(msg)

                else:
                    self.callback.log("Success building %s" % os.path.basename(pkg))
                    built_pkgs.append(pkg)
                    # createrepo with the new pkgs
                    for d in [self.destdir, chroot_dir]:
                        rc, out, err = createrepo(d)
                        if err.strip():
                            self.callback.error("Error making local repo: %s" % d)
                            self.callback.error("%s" % err)
                            #FIXME - maybe clean up .repodata and .olddata here?

            if self.failed:
                if len(self.failed) != len(to_be_built):
                    to_be_built = self.failed
                    try_again = True
                    self.callback.log('Trying to rebuild %s failed pkgs' % len(self.failed))
                else:
                    self.callback.log("Tried twice - following pkgs could not be successfully built:")
                    for pkg in self.failed:
                        msg = pkg
                        if pkg in downloaded_pkgs:
                            msg = downloaded_pkgs[pkg]
                        self.callback.log(msg)

                    try_again = False
            else:
                try_again = False



def parse_args(args):

    parser = SortedOptParser("mockremote -b hostname -u user -r chroot pkg pkg pkg")
    parser.add_option('-r', '--root', default=DEF_CHROOT, dest='chroot',
            help="chroot config name/base to use in the mock build")
    parser.add_option('-c', '--continue', default=False, action='store_true',
            dest='cont',
            help="if a pkg fails to build, continue to the next one")
    parser.add_option('-a', '--addrepo', default=DEF_REPOS, action='append',
            dest='repos',
            help="add these repo baseurls to the chroot's yum config")
    parser.add_option('--recurse', default=False, action='store_true',
            help="if more than one pkg and it fails to build, try to build the rest and come back to it")
    parser.add_option('--log', default=None, dest='logfile',
            help="log to the file named by this option, defaults to not logging")
    parser.add_option("-b", "--builder", dest='builder', default=None,
             help="builder to use")
    parser.add_option("-u", dest="user", default=DEF_USER,
         help="user to run as/connect as on builder systems")
    parser.add_option("-t", "--timeout", dest="timeout", type="int",
          default=DEF_TIMEOUT, help="maximum time in seconds a build can take to run")
    parser.add_option("--destdir", dest="destdir", default=DEF_DESTDIR,
           help="place to download all the results/packages")
    parser.add_option("--packages", dest="packages_file", default=None,
           help="file to read list of packages from")
    parser.add_option("-q", "--quiet", dest="quiet", default=False, action="store_true",
           help="output very little to the terminal")

    opts, args = parser.parse_args(args)

    if not opts.builder:
        sys.stderr.write("Must specify a system to build on")
        sys.exit(1)

    if opts.packages_file and os.path.exists(opts.packages_file):
        args.extend(read_list_from_file(opts.packages_file))

    #args = list(set(args)) # poor man's 'unique' - this also changes the order
    # :(

    if not args:
        sys.stderr.write("Must specify at least one pkg to build")
        sys.exit(1)

    if not opts.chroot:
        sys.stderr.write("Must specify a mock chroot")
        sys.exit(1)

    for url in opts.repos:
        if not (url.startswith('http://') or url.startswith('https://') or  url.startswith('file://')):
            sys.stderr.write("Only http[s] or file urls allowed for repos")
            sys.exit(1)

    return opts, args


#FIXME
# play with createrepo run at the end of each build
# need to output the things that actually worked :)


def main(args):

    # parse args
    opts, pkgs = parse_args(args)

    if not os.path.exists(opts.destdir):
        os.makedirs(opts.destdir)

    try:
        # setup our callback
        callback = CliLogCallBack(logfn=opts.logfile, quiet=opts.quiet)
        # our mockremote instance
        mr = MockRemote(builder=opts.builder, user=opts.user,
               timeout=opts.timeout, destdir=opts.destdir, chroot=opts.chroot,
               cont=opts.cont, recurse=opts.recurse, repos=opts.repos,
               callback=callback)

        # FIXMES
        # things to think about doing:
        # output the remote tempdir when you start up
        # output the number of pkgs
        # output where you're writing things to
        # consider option to sync over destdir to the remote system to use
        # as a local repo for the build
        #

        if not opts.quiet:
            print "Building %s pkgs" % len(pkgs)

        mr.build_pkgs(pkgs)

        if not opts.quiet:
            print "Output written to: %s" % mr.destdir

    except MockRemoteError, e:
        print >> sys.stderr, "Error on build:"
        print >> sys.stderr, str(e)
        return


if __name__ == '__main__':
    main(sys.argv[1:])
