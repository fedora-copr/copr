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
from jinja2 import Environment, FileSystemLoader
from simplejson.scanner import JSONDecodeError
from copr_rpmbuild.helpers import SourceType, run_cmd
from copr_rpmbuild.providers.distgit import DistGitProvider

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin


CONF_DIRS = [os.path.dirname(os.path.realpath(__file__)),
             "/etc/copr-rpmbuild"]

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler(sys.stdout))


class MockBuilder(object):
    def __init__(self, task, srpm, resultdir=None, confdirs=None):
        self.srpm = srpm
        self.task_id = task["task_id"]
        self.chroot = task["chroot"]
        self.buildroot_pkgs = task["buildroot_pkgs"]
        self.enable_net = task["enable_net"]
        self.repos = None
        self.use_bootstrap_container = None
        self.pkg_manager_conf = "dnf" if "custom-1" not in task["chroot"] else "yum"
        self.resultdir = resultdir
        self.confdirs = confdirs

    def run(self):
        configdir = os.path.join(self.resultdir, "configs")
        os.makedirs(configdir)
        shutil.copy2("/etc/mock/site-defaults.cfg", configdir)
        shutil.copy2("/etc/mock/{0}.cfg".format(self.chroot), configdir)
        cfg = self.render_config_template()
        with open(os.path.join(configdir, "child.cfg"), "w") as child:
            child.write(cfg)

        result = self.produce_rpm(self.srpm, configdir, self.resultdir)
        log.info(result)

    def render_config_template(self):
        jinja_env = Environment(loader=FileSystemLoader(self.confdirs))
        template = jinja_env.get_template("mock.cfg.j2")
        return template.render(chroot=self.chroot, task_id=self.task_id, buildroot_pkgs=self.buildroot_pkgs,
                               enable_net=self.enable_net, use_bootstrap_container=self.use_bootstrap_container,
                               repos=self.repos, pkg_manager_conf=self.pkg_manager_conf)

    def produce_rpm(self, srpm, configdir, resultdir):
        cmd = ["/usr/bin/mock",
               "--rebuild", srpm,
               "--configdir", configdir,
               "--resultdir", resultdir,
               "--no-clean", "-r", "child"]
        return run_cmd(cmd)

    def touch_success_file(self):
        with open(os.path.join(self.resultdir, "success"), "w") as success:
            success.write("done")


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

    config = configparser.RawConfigParser(defaults={
        "resultdir": "/var/lib/copr-rpmbuild/results",
        "lockfile": "/var/lib/copr-rpmbuild/lockfile",
        "logfile": "/var/lib/copr-rpmbuild/main.log",
    })
    config_paths = [os.path.join(path, "main.ini") for path in CONF_DIRS]
    config.read(args.config or reversed(config_paths))
    if not config.sections():
        log.error("No configuration file main.ini in: {}".format(" ".join(CONF_DIRS)))
        sys.exit(1)

    # Log also to a file
    log.addHandler(logging.FileHandler(config.get("main", "logfile")))

    # Allow only one instance
    lock = lockfile.LockFile(config.get("main", "lockfile"))
    try:
        lock.acquire(timeout=0)
        init(args,config)
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
    task = get_task("/get-build-task/", args.task_id, config)

    # @TODO Select the provider based on source_type
    workdir = tempfile.mkdtemp()
    provider = DistGitProvider(task["source_json"], workdir, CONF_DIRS)
    provider.run()
    shutil.copy2(provider.srpm, config.get("main", "resultdir"))


def build_rpm(args, config):
    task = get_task("/get-srpm-build-task/", args.task_id, config)

    workdir = tempfile.mkdtemp()
    provider = DistGitProvider(task["source_json"], workdir, CONF_DIRS)
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
