#!/usr/bin/env python3

import re
import os
import sys
import argparse
import requests
import json
import logging
import tempfile
import shutil
import lockfile
import configparser
from simplejson.scanner import JSONDecodeError
from copr_rpmbuild import providers
from copr_rpmbuild.builders.mock import MockBuilder

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin


CONF_DIRS = [os.path.dirname(os.path.realpath(__file__)),
             "/etc/copr-rpmbuild"]

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler(sys.stdout))


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


def main():
    parser = argparse.ArgumentParser(description="Runs COPR build of the specified task ID,"
                                                 "e.g. 551347-epel-7-x86_64, and puts results"
                                                 "into /var/lib/copr-rpmbuild/results/.")
    parser.add_argument("task_id", type=str, help="COPR task-id to be built (e.g. 551347-epel-7-x86_64)")
    parser.add_argument("-c", "--config", type=str, help="Use specific configuration .ini file")
    parser.add_argument("-d", "--detached", action="store_true", help="Run build in background."
                                                                      "Log into /var/lib/copr-rpmbuild/main.log")
    parser.add_argument("-v", "--verbose", action="count", help="print debugging information")
    parser_output = parser.add_mutually_exclusive_group(required=True)
    parser_output.add_argument("--rpm", action="store_true")
    parser_output.add_argument("--srpm", action="store_true")
    args = parser.parse_args()

    if args.detached:
        daemonize()

    config = configparser.RawConfigParser(defaults={
        "resultdir": "/var/lib/copr-rpmbuild/results",
        "lockfile": "/var/lib/copr-rpmbuild/lockfile",
        "logfile": "/var/lib/copr-rpmbuild/main.log",
        "pidfile": "/var/lib/copr-rpmbuild/pid",
    })
    config_paths = [os.path.join(path, "main.ini") for path in CONF_DIRS]
    config.read(args.config or reversed(config_paths))
    if not config.sections():
        log.error("No configuration file main.ini in: {}".format(" ".join(CONF_DIRS)))
        sys.exit(1)

    # Write pid
    pidfile = open(config.get("main", "pidfile"), "w")
    pidfile.write(str(os.getpid()))
    pidfile.close()

    # Log also to a file
    log.addHandler(logging.FileHandler(config.get("main", "logfile")))

    # Allow only one instance
    lock = lockfile.LockFile(config.get("main", "lockfile"))
    try:
        lock.acquire(timeout=0)
        init(args, config)
        action = build_srpm if args.srpm else build_rpm
        action(args, config)
    except (lockfile.LockError, RuntimeError, IOError) as ex:
        log.error(ex)
        sys.exit(1)
    finally:
        if lock.i_am_locking():
            lock.release()


def init(args, config):
    resultdir = config.get("main", "resultdir")
    if os.path.exists(resultdir):
        shutil.rmtree(resultdir)
    os.makedirs(resultdir)


def build_srpm(args, config):
    task = get_task("/backend/get-srpm-build-task/", args.task_id, config)

    workdir = tempfile.mkdtemp()
    provider = providers.factory(task["source_type"])(
        task["source_json"], workdir, CONF_DIRS)
    provider.run()
    shutil.copy2(provider.srpm, config.get("main", "resultdir"))


def build_rpm(args, config):
    task = get_task("/backend/get-build-task/", args.task_id, config)

    workdir = tempfile.mkdtemp()
    provider = providers.DistGitProvider(task["source_json"], workdir, CONF_DIRS)
    provider.run()

    resultdir = config.get("main", "resultdir")
    builder = MockBuilder(task, provider.srpm, resultdir=resultdir, confdirs=CONF_DIRS)
    builder.run()
    builder.touch_success_file()


def get_task(endpoint, id, config):
    try:
        url = urljoin(urljoin(config.get("main", "frontend_url"), endpoint), id)
        response = requests.get(url)
        task = response.json()
        task["source_json"] = json.loads(task["source_json"])
        return task
    except JSONDecodeError:
        raise RuntimeError("No valid task {}".format(url))


if __name__ == "__main__":
    main()
