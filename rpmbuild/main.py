#!/usr/bin/python3

import os
import fcntl
import subprocess
import sys
import argparse
import json
import logging
import shutil
import pprint
import shlex

from urllib.parse import urljoin, urlencode

import daemon

from copr_common.request import SafeRequest, RequestError
from copr_common.helpers import nullcontext
from copr_rpmbuild import providers
from copr_rpmbuild.builders.mock import MockBuilder
from copr_rpmbuild.automation import run_automation_tools
from copr_rpmbuild.helpers import (
    read_config,
    parse_copr_name,
    filter_our_output,
    copr_chroot_to_task_id,
    macros_for_task,
    locate_srpm,
)

from copr_rpmbuild import __version__

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
log.addHandler(logging.StreamHandler(sys.stdout))


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
    base_parser.add_argument("--version", action="version", version="%(prog)s version " + __version__)
    base_parser.add_argument("--build-id", type=str, help="COPR build ID")
    base_parser.add_argument("--copr", type=str, help="copr for which to build, e.g. @group/project")

    base_parser.add_argument("--task-url", help="Full URL to a json task definition")
    base_parser.add_argument("--task-file", help="Path to a local json file with task definition")

    return base_parser


def main_daemon(args, config):
    """
    Part of the copr-rpmbuild logic that is run as daemon, if --detached.
    """

    # Filter out terminal control sequences from stdout/stderr and copy the
    # output to a logfile.
    logfile = config.get("main", "logfile")
    proc_loggify = filter_our_output("/usr/bin/copr-rpmbuild-loggify", logfile)

    # Write PGID, so 'copr-rpmbuild-cancel' knows where to send signals
    main_pid = os.getpgrp()
    with open(config.get("main", "pidfile"), "w", encoding="utf-8") as pidfd:
        pidfd.write(str(main_pid))

    # Write logger pid, so copr-rpmbuild-log can wait for us.
    with open(config.get("main", "logger_pidfile"), "w", encoding="utf-8") as pidfile:
        pidfile.write(f"{proc_loggify.pid}\n")

    cmd = " ".join(map(shlex.quote, sys.argv))
    log.info('\nYou can reproduce this build on your computer by running:\n')
    log.info('  sudo dnf install copr-rpmbuild')
    log.info('  %s\n\n', cmd.replace(" --detached", ""))
    log.info('Version: %s', __version__)
    log.info("PID: %s", main_pid)
    log.info("Logging PID: %s", proc_loggify.pid)

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
    except RequestError as ex:
        log.error("Network error: %s", ex)
        sys.exit(1)
    except RuntimeError as e:
        log.error("Copr build error: %s", e)
        sys.exit(1)
    except OSError:
        log.exception("")
        sys.exit(1)
    except: # Programmer's mistake
        log.exception("")
        raise
    finally:
        fcntl.lockf(lockfd, fcntl.LOCK_UN, 1)
        os.close(lockfd)


def init(args, config):
    resultdir = config.get("main", "resultdir")
    if os.path.exists(resultdir) and args.drop_resultdir:
        shutil.rmtree(resultdir)
        os.makedirs(resultdir)


def produce_srpm(task, config):
    """
    Use *Provider() classes to create source RPM in config.get("resultdir")
    """
    try:
        macros = macros_for_task(task, config)
        clazz = providers.factory(task["source_type"])
        provider = clazz(task["source_json"], config, macros=macros, task=task)
        provider.produce_srpm()
        provider.copy_insecure_results()
    finally:
        provider.cleanup()


def get_task(args, config, build_config_url_path=None, task_id=None):
    task = {
        'task_id': task_id,
        'source_type': None,
        'source_json': {}
    }

    if args.task_file:
        task.update(read_task_from_file(args.task_file))
    elif args.task_url:
        task.update(get_vanilla_build_config(args.task_url))
    elif build_config_url_path:
        url = urljoin(config.get("main", "frontend_url"), build_config_url_path)
        task.update(get_vanilla_build_config(url))

    if task.get("source_json"):
        task["source_json"] = json.loads(task["source_json"])

    if args.chroot:
        task['chroot'] = args.chroot

    if args.copr:
        task['task_id'] = copr_chroot_to_task_id(args.copr, args.chroot)

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

    produce_srpm(task, config)

    resultdir = config.get("main", "resultdir")
    log.info("Output: {0}".format(
        list(entry.name for entry in os.scandir(resultdir))))

    # extract spec file from SRPM
    cmd = f"rpm2archive -n < {locate_srpm(resultdir)} | tar xf - '*.spec'"
    subprocess.run(cmd, shell=True, check=False, cwd=resultdir)

    with open(os.path.join(resultdir, 'success'), "w") as success:
        success.write("done")
    run_automation_tools(task, resultdir, None, log, config)


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

    try:
        source_json = {
            "clone_url": task["git_repo"],
            "committish": task["git_hash"],
        }
        distgit = providers.DistGitProvider(source_json, config)

        # Just clone and download sources, don't create source RPM (aka
        # produce_srpm).  We want to create the source RPM using Mock
        # in the target chroot.
        distgit.produce_sources()
        resultdir = config.get("main", "resultdir")
        builder = MockBuilder(task, distgit.clone_to, resultdir, config)
        builder.run()
        builder.touch_success_file()
        run_automation_tools(
            task, resultdir, builder.mock_config_file, log, config)
    finally:
        builder.archive_configs()
        distgit.cleanup()


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

    builder.prepare_configs()
    log.info("Wrote: %s", builder.mock_config_file)


def get_vanilla_build_config(url):
    try:
        request = SafeRequest(log=log)
        response = request.get(url)
        build_config = response.json()
        if not build_config:
            raise RuntimeError("No valid build_config at {0}".format(url))
        return build_config

    except json.decoder.JSONDecodeError as ex:
        raise RuntimeError("No valid build_config at {0}".format(url)) from ex


def read_task_from_file(path):
    try:
        with open(path, "r") as f:
            return json.loads(f.read())
    except OSError as ex:
        raise RuntimeError(ex)
    except json.decoder.JSONDecodeError as ex:
        raise RuntimeError("No valid build_config at {0}".format(path)) from ex


def _main():
    parser = get_parser()
    args = parser.parse_args()
    config = read_config(args.config)
    if args.verbose:
        log.setLevel(logging.DEBUG)

    context = daemon.DaemonContext(umask=0o22) if args.detached else nullcontext()
    with context:
        main_daemon(args, config)


if __name__ == "__main__":
    sys.exit(_main())
