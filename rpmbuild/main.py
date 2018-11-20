#!/usr/bin/python3

import re
import os
import fcntl
import sys
import argparse
import requests
import json
import logging
import tempfile
import shutil
import pprint
import tempfile
import stat
import pipes
import pkg_resources

try:
    from simplejson.scanner import JSONDecodeError
except ImportError:
    JSONDecodeError = Exception

from copr_rpmbuild import providers
from copr_rpmbuild.builders.mock import MockBuilder
from copr_rpmbuild.helpers import read_config, extract_srpm, locate_srpm, \
     SourceType, parse_copr_name, dump_live_log, copr_chroot_to_task_id

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin

try:
    from urllib.parse import urlencode
except ImportError:
    from urllib import urlencode

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stdout))

try:
    VERSION = pkg_resources.require('copr-rpmbuild')[0].version
except pkg_resources.DistributionNotFound:
    VERSION = 'git'

def daemonize():
    try:
        pid = os.fork()
    except OSError as e:
        self.log.error("Unable to fork, errno: {0}".format(e.errno))
        sys.exit(1)

    if pid != 0:
        log.info(pid)
        os._exit(0)

    process_id = os.setsid()
    if process_id == -1:
        sys.exit(1)

    devnull_fd = os.open('/dev/null', os.O_RDWR)
    os.dup2(devnull_fd, 0)
    os.dup2(devnull_fd, 1)
    os.dup2(devnull_fd, 2)
    os.close(devnull_fd)


def get_parser():
    shared_parser = argparse.ArgumentParser(add_help=False)
    shared_parser.add_argument("-d", "--detached", default=False, action="store_true",
                               help="Run build in background. Log into /var/lib/copr-rpmbuild/main.log.")
    shared_parser.add_argument("-v", "--verbose", action="count",
                               help="Print debugging information.")
    shared_parser.add_argument("-r", "--chroot",
                               help="Name of the chroot to build rpm package in (e.g. epel-7-x86_64).")
    shared_parser.add_argument("--drop-resultdir", action="store_true",
                               help="Drops resultdir and its content at the beggining before continuing.")

    product = shared_parser.add_mutually_exclusive_group()
    product.add_argument("--rpm", action="store_true", help="Build rpms. This is the default action.")
    product.add_argument("--srpm", action="store_true", help="Build srpm.")
    product.add_argument("--dump-configs", action="store_true", help="Only dump configs, without actual building.")
    #product.add_argument("--tgz", action="store_true", help="Make tar.gz with build sources, spec and patches.")

    base_parser = argparse.ArgumentParser(description="COPR building tool.", parents=[shared_parser])
    base_parser.add_argument("-c", "--config", type=str, help="Use specific configuration .ini file.")
    base_parser.add_argument("--version", action="version", version="%(prog)s version " + VERSION)
    base_parser.add_argument("--build-id", type=str, help="COPR build ID")
    base_parser.add_argument("--copr", type=str, help="copr for which to build, e.g. @group/project")

    subparsers = base_parser.add_subparsers(title="submodes", dest="submode")
    scm_parser = subparsers.add_parser("scm", parents=[shared_parser],
                                       help="Build from an SCM repository.")

    scm_parser.add_argument("--clone-url", required=True,
                            help="clone url to a project versioned by Git or SVN, required")
    scm_parser.add_argument("--commit", dest="committish", default="",
                            help="branch name, tag name, or git hash to be built")
    scm_parser.add_argument("--subdir", dest="subdirectory", default="",
                            help="relative path from the repo root to the package content")
    scm_parser.add_argument("--spec", default="",
                            help="relative path from the subdirectory to the .spec file")
    scm_parser.add_argument("--type", dest="type", choices=["git", "svn"], default="git",
                            help="Specify versioning tool. Default is 'git'.")
    scm_parser.add_argument("--method", dest="srpm_build_method", default="rpkg",
                            choices=["rpkg", "tito", "tito_test", "make_srpm"],
                            help="Srpm build method. Default is 'rpkg'.")

    subparsers.add_parser("default") # python 2.7 hack

    return base_parser


def main():
    # hack for 2.7;  optional sub-parsers are supported since python 3.4?
    if 'scm' not in sys.argv:
        sys.argv.append('default')

    parser = get_parser()
    args = parser.parse_args()
    config = read_config(args.config)

    if args.verbose:
        log.setLevel(logging.DEBUG)

    if args.detached:
        daemonize()

    # Write pid
    pidfile = open(config.get("main", "pidfile"), "w")
    pidfile.write(str(os.getpid()))
    pidfile.close()

    # Log also to a file
    logfile = config.get("main", "logfile")
    if logfile:
        open(logfile, 'w').close() # truncate log
        dump_live_log(logfile)

    log.info('Running: {0}'.format(" ".join(map(pipes.quote, sys.argv))))
    log.info('Version: {0}'.format(VERSION))

    # Allow only one instance
    lockfd = os.open(config.get("main", "lockfile"), os.O_RDWR | os.O_CREAT)
    try:
        fcntl.lockf(lockfd, fcntl.LOCK_EX, 1)
        init(args, config)

        if args.dump_configs:
            action = dump_configs
        elif args.srpm:
            action = build_srpm
        else:
            action = build_rpm

        action(args, config)
    except (RuntimeError, OSError):
        log.exception("")
        sys.exit(1)
    except: # Programmer's mistake
        log.exception("")
        sys.exit(1)
    finally:
        fcntl.lockf(lockfd, fcntl.LOCK_UN, 1)
        os.close(lockfd)


def init(args, config):
    resultdir = config.get("main", "resultdir")
    if os.path.exists(resultdir) and args.drop_resultdir:
        shutil.rmtree(resultdir)
        os.makedirs(resultdir)


def produce_srpm(task, config, resultdir):
    """
    create tempdir to allow --private-users=pick with make_srpm
    that changes permissions on the result directory to out of scope values
    """
    tempdir = tempfile.mkdtemp(prefix=resultdir)
    os.chmod(tempdir, stat.S_IRWXU|stat.S_IRWXO)
    provider = providers.factory(task["source_type"])(
        task["source_json"], tempdir, config)
    provider.produce_srpm()
    for item in os.listdir(tempdir):
        shutil.copy(os.path.join(tempdir, item), resultdir)
    shutil.rmtree(tempdir)


def get_task(args, config, build_config_url_path=None, task_id=None):
    task = {
        'task_id': task_id,
        'source_type': None,
        'source_json': {}
    }

    if build_config_url_path:
        task.update(
            get_vanilla_build_config(
                build_config_url_path, config))

    if args.chroot:
        task['chroot'] = args.chroot

    if args.copr:
        task['task_id'] = copr_chroot_to_task_id(args.copr, args.chroot)

    if args.submode == 'scm':
        task['source_type'] = SourceType.SCM
        task['source_json'].update({
            'clone_url': args.clone_url,
            'committish': args.committish,
            'subdirectory': args.subdirectory,
            'spec': args.spec,
            'type': args.type,
            'srpm_build_method': args.srpm_build_method,
        })

    return task


def log_task(task):
    pp = pprint.PrettyPrinter(width=120)
    log.info("Task:\n"+pp.pformat(task)+'\n')


def build_srpm(args, config):
    if args.chroot:
        raise RuntimeError("--chroot option is not supported with --srpm")

    if args.build_id:
        build_config_url_path = urljoin("/backend/get-srpm-build-task/", args.build_id)
    elif args.copr:
        raise RuntimeError("--copr option is not supported with --srpm")
    else:
        build_config_url_path = None

    task = get_task(args, config, build_config_url_path)
    log_task(task)

    resultdir = config.get("main", "resultdir")
    produce_srpm(task, config, resultdir)

    log.info("Output: {0}".format(
        os.listdir(resultdir)))

    with open(os.path.join(resultdir, 'success'), "w") as success:
        success.write("done")


def build_rpm(args, config):
    if not args.chroot:
        raise RuntimeError("Missing --chroot parameter")

    task_id = None
    build_config_url_path = None

    if args.build_id:
        task_id = "-".join([args.build_id, args.chroot])
        build_config_url_path = urljoin("/backend/get-build-task/", task_id)
    elif args.copr:
        ownername, projectname = parse_copr_name(args.copr)
        get_params = {
            'ownername': ownername,
            'projectname': projectname,
            'chrootname': args.chroot,
        }
        build_config_url_path = ("/api_3/project-chroot/build-config?"
                                 + urlencode(get_params))

    task = get_task(args, config, build_config_url_path, task_id)
    log_task(task)

    sourcedir = tempfile.mkdtemp()
    scm_provider = providers.ScmProvider(task["source_json"], sourcedir, config)

    if task.get("fetch_sources_only"):
        scm_provider.produce_sources()
    else:
        scm_provider.produce_srpm()
        built_srpm = locate_srpm(sourcedir)
        extract_srpm(built_srpm, sourcedir)

    resultdir = config.get("main", "resultdir")
    builder = MockBuilder(task, sourcedir, resultdir, config)
    builder.run()
    builder.touch_success_file()
    shutil.rmtree(sourcedir)


def dump_configs(args, config):
    if not args.chroot:
        raise RuntimeError("Missing --chroot parameter")

    task_id = None
    build_config_url_path = None

    if args.build_id:
        task_id = "-".join([args.build_id, args.chroot])
        build_config_url_path = urljoin("/backend/get-build-task/", task_id)
    elif args.copr:
        ownername, projectname = parse_copr_name(args.copr)
        get_params = {
            'ownername': ownername,
            'projectname': projectname,
            'chrootname': args.chroot,
        }
        build_config_url_path = ("/api_3/project-chroot/build-config?"
                                 + urlencode(get_params))

    task = get_task(args, config, build_config_url_path, task_id)
    log_task(task)

    resultdir = config.get("main", "resultdir")
    builder = MockBuilder(task, None, resultdir, config)

    configdir = os.path.join(resultdir, "configs")
    config_paths = builder.prepare_configs(configdir)
    for config_path in config_paths:
        log.info("Wrote: "+config_path)


def get_vanilla_build_config(build_config_url_path, config):
    try:
        url = urljoin(config.get("main", "frontend_url"), build_config_url_path)
        response = requests.get(url)
        build_config = response.json()

        if not build_config:
            raise RuntimeError("No valid build_config at {0}".format(url))

        if build_config.get("source_json"):
            build_config["source_json"] = json.loads(build_config["source_json"])
    except JSONDecodeError:
        raise RuntimeError("No valid build_config at {0}".format(url))


    return build_config


if __name__ == "__main__":
    main()
