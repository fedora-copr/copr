"""
copr-distgit-client code, moved to module to simplify unit-testing
"""

import argparse
import configparser
import errno
import glob
import logging
import pipes
import os
import subprocess
from six.moves.urllib.parse import urlparse


def log_cmd(command, comment="Running command"):
    """ Dump the command to stderr so it can be c&p to shell """
    command = ' '.join([pipes.quote(x) for x in command])
    logging.info("%s: %s", comment, command)


def check_output(cmd, comment="Reading stdout from command"):
    """ el6 compatible subprocess.check_output() """
    log_cmd(cmd, comment)
    process = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, _) = process.communicate()
    if process.returncode:
        raise RuntimeError("Exit non-zero: {0}".format(process.returncode))
    return stdout

def call(cmd, comment="Calling"):
    """ wrap sp.call() with logging info """
    log_cmd(cmd, comment)
    return subprocess.call(cmd)

def check_call(cmd, comment="Checked call"):
    """ wrap sp.check_call() with logging info """
    log_cmd(cmd, comment)
    subprocess.check_call(cmd)

def _load_configfile(filename):
    config = configparser.ConfigParser()
    config.read(filename)


def _load_config(directory):
    config = configparser.ConfigParser()
    files = glob.glob(os.path.join(directory, "*.ini"))
    logging.debug("Files %s in config directory %s", files, directory)
    config.read(files)

    config_dict = {
        "instances": {},
        "clone_host_map": {},
    }

    instances = config_dict["instances"]
    for section_name in config.sections():
        section = config[section_name]
        instance = instances[section_name] = {}
        for key in section.keys():
            # array-like config options
            if key in ["clone_hostnames"]:
                hostnames = section[key].split()
                instance[key] = [h.strip() for h in hostnames]
            else:
                instance[key] = section[key]

        for key in ["sources", "specs"]:
            if key in instance:
                continue
            instance[key] = "."

        if "sources_file" not in instance:
            instance["sources_file"] = "sources"

        if "default_sum" not in instance:
            instance["default_sum"] = "md5"

        for host in instance["clone_hostnames"]:
            config_dict["clone_host_map"][host] = instance

    return config_dict


def download(url, filename):
    """ Download URL as FILENAME using curl command """
    command = [
        "curl",
        "-H", "Pragma:",
        "-o", filename,
        "--location",
        "--remote-time",
        "--show-error",
        "--fail",
        url,
    ]

    if call(command):
        raise RuntimeError("Can't download file {0}".format(filename))


def mkdir_p(path):
    """ mimic 'mkdir -p <path>' command """
    try:
        os.makedirs(path)
    except OSError as err:
        if err.errno != errno.EEXIST:
            raise


def download_file_and_check(url, params, distgit_config):
    """ Download given URL (if not yet downloaded), and try the checksum """
    filename = params["filename"]
    sum_binary = params["hashtype"] + "sum"

    mkdir_p(distgit_config["sources"])

    if not os.path.exists(filename):
        logging.info("Downloading %s", filename)
        download(url, filename)
    else:
        logging.info("File %s already exists", filename)

    sum_command = [sum_binary, filename]
    output = check_output(sum_command).decode("utf-8")
    checksum, _ = output.strip().split()
    if checksum != params["hash"]:
        raise RuntimeError("Check-sum {0} is wrong, expected: {1}".format(
            checksum,
            params["hash"],
        ))


def get_distgit_config(config):
    """
    Given the '.git/config' file from current directory, return the
    appropriate part of dist-git configuration.
    Returns tuple: (urlparse(clone_url), distgit_config)
    """
    git_config = ".git/config"
    if not os.path.exists(git_config):
        msg = "{0} not found, $PWD is not a git repository".format(git_config)
        raise RuntimeError(msg)

    git_conf_reader = configparser.ConfigParser()
    git_conf_reader.read(git_config)
    url = git_conf_reader['remote "origin"']["url"]
    parsed_url = urlparse(url)
    if parsed_url.hostname is None:
        hostname = "localhost"
    else:
        hostname = parsed_url.hostname
    return parsed_url, config["clone_host_map"][hostname]


def get_spec(distgit_config):
    """
    Find the specfile name inside distgit_config["specs"] directory
    """
    specfiles = glob.glob(os.path.join(distgit_config["specs"], '*.spec'))
    if len(specfiles) != 1:
        raise RuntimeError("Exactly one spec file expected")
    specfile = os.path.basename(specfiles[0])
    return specfile


def sources(args, config):
    """
    Locate the sources, and download them from the appropriate dist-git
    lookaside cache.
    """
    parsed_url, distgit_config = get_distgit_config(config)
    namespace = parsed_url.path.lstrip('/').split('/')
    # drop the last {name}.git part
    repo_name = namespace.pop()
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    namespace = list(reversed(namespace))

    output = check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    output = output.decode("utf-8").strip()
    if output == "HEAD":
        output = check_output(["git", "rev-parse", "HEAD"])
        output = output.decode("utf-8").strip()
    refspec = output
    specfile = get_spec(distgit_config)
    name = specfile[:-5]
    sources_file = distgit_config["sources_file"].format(name=name)
    if not os.path.exists(sources_file):
        raise RuntimeError("{0} file not found".format(sources_file))

    logging.info("Reading sources specification file: %s", sources_file)
    with open(sources_file, 'r') as sfd:
        while True:
            line = sfd.readline()
            if not line:
                break

            kwargs = {
                "name": repo_name,
                "refspec": refspec,
                "namespace": namespace,
            }

            source_spec = line.split()
            if len(source_spec) == 2:
                # old md5/sha1 format: 0ced6f20b9fa1bea588005b5ad4b52c1  tar-1.26.tar.xz
                kwargs["hashtype"] = distgit_config["default_sum"].lower()
                kwargs["hash"] = source_spec[0]
                kwargs["filename"] = source_spec[1]
            elif len(source_spec) == 4:
                # SHA512 (tar-1.30.tar.xz.sig) = <HASH>
                kwargs["hashtype"] = source_spec[0].lower()
                kwargs["hash"] = source_spec[3]
                filename = os.path.basename(source_spec[1])
                kwargs["filename"] = filename.strip('()')
            else:
                msg = "Weird sources line: {0}".format(line)
                raise RuntimeError(msg)

            url_file = '/'.join([
                distgit_config["lookaside_location"],
                distgit_config["lookaside_uri_pattern"].format(**kwargs)
            ])

            download_file_and_check(url_file, kwargs, distgit_config)


def srpm(args, config):
    """
    Using the appropriate dist-git configuration, generate source RPM
    file.  This requires running 'def sources()' first.
    """
    _, distgit_config = get_distgit_config(config)

    cwd = os.getcwd()
    sources_dir = os.path.join(cwd, distgit_config["sources"])
    specs = os.path.join(cwd, distgit_config["specs"])
    spec = get_spec(distgit_config)

    mkdir_p(args.outputdir)

    spec_abspath = os.path.join(specs, spec)

    if args.mock_chroot:
        command = [
            "mock", "--buildsrpm",
            "-r", args.mock_chroot,
            "--spec", spec_abspath,
            "--sources", sources_dir,
            "--resultdir", args.outputdir,
        ]
    else:
        command = [
            "rpmbuild", "-bs", spec_abspath,
            "--define", "dist %nil",
            "--define", "_sourcedir {0}".format(sources_dir),
            "--define", "_srcrpmdir {0}".format(args.outputdir),
            "--define", "_disable_source_fetch 1",
        ]

    if args.dry_run or 'COPR_DISTGIT_CLIENT_DRY_RUN' in os.environ:
        log_cmd(command, comment="Dry run")
    else:
        check_call(command)


def _get_argparser():
    parser = argparse.ArgumentParser(prog="copr-distgit-client",
                                     description="""\
A simple, configurable python utility that is able to download sources from
various dist-git instances, and generate source RPMs.
The utility is able to automatically map the .git/config clone URL into the
corresponding dist-git instance configuration.
""")

    # main parser
    default_confdir = os.environ.get("COPR_DISTGIT_CLIENT_CONFDIR",
                                     "/etc/copr-distgit-client")
    parser.add_argument(
        "--configdir", default=default_confdir,
        help="Where to load configuration files from")
    parser.add_argument(
        "--loglevel", default="info",
        help="Python logging level, e.g. debug, info, error")
    subparsers = parser.add_subparsers(
        title="actions", dest="action")

    # sources parser
    subparsers.add_parser(
        "sources",
        description=(
            "Using the 'url' .git/config, detect where the right DistGit "
            "lookaside cache exists, and download the corresponding source "
            "files."),
        help="Download sources from the lookaside cache")

    # srpm parser
    srpm_parser = subparsers.add_parser(
        "srpm",
        help="Generate a source RPM",
        description=(
            "Generate a source RPM from the downloaded source files "
            "by 'sources' command, please run 'sources' first."),
    )
    srpm_parser.add_argument(
        "--outputdir",
        default="/tmp",
        help="Where to store the resulting source RPM")
    srpm_parser.add_argument(
        "--mock-chroot",
        help=("Generate the SRPM in mock buildroot instead of on host.  The "
              "argument is passed down to mock as the 'mock -r|--root' "
              "argument."),
    )
    srpm_parser.add_argument(
        "--dry-run", action="store_true",
        help=("Don't produce the SRPM, just print the command which would be "
              "otherwise called"),
    )
    return parser


def main():
    """ The entrypoint for the whole logic """
    args = _get_argparser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.loglevel.upper()),
        format="%(levelname)s: %(message)s",
    )
    config = _load_config(args.configdir)

    if args.action == "srpm":
        srpm(args, config)
    else:
        sources(args, config)
