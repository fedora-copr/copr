import re
import os
import sys
import argparse
import subprocess
import requests
import json
import munch
import logging
import tempfile
import shutil
import ConfigParser
from jinja2 import Environment, FileSystemLoader

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin


log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log.addHandler(logging.StreamHandler(sys.stdout))
log.addHandler(logging.FileHandler("builder-live.log"))


def run_cmd(cmd, cwd=".", raise_on_error=True):
    """
    Runs given command in a subprocess.

    :param list(str) cmd: command to be executed and its arguments
    :param str workdir: In which directory to execute the command
    :param bool raise_on_error: if PackageImportException should be raised on error

    :raises PackageImportException
    :returns munch.Munch(cmd, stdout, stderr, returncode)
    """
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)
    try:
        (stdout, stderr) = process.communicate()
    except OSError as e:
        raise RuntimeError(str(e))

    result = munch.Munch(
        cmd = cmd,
        stdout = stdout.strip(),
        stderr = stderr.strip(),
        returncode = process.returncode
    )
    log.debug(result)

    if result.returncode != 0:
        raise RuntimeError(result.stderr)

    return result


class SourceType:
    LINK = 1
    UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6
    DISTGIT = 7


class DistGitProvider(object):
    def __init__(self, source_json, workdir=None):
        self.clone_url = source_json["clone_url"]
        self.branch = source_json["branch"]
        self.workdir = workdir

    def run(self):
        repodir = os.path.join(self.workdir, "repo")
        result = self.clone(repodir)
        log.info(result)

        cfg = self.render_rpkg_template()
        log.info(cfg)

        config_path = os.path.join(self.workdir, "rpkg.conf")
        f = open(config_path, "w+")
        f.write(cfg)
        f.close()

        if self.branch:
            self.checkout(self.branch, repodir)

        module_name = self.module_name(self.clone_url)
        result = self.produce_srpm(config_path, module_name, repodir)
        log.info(result)

    def clone(self, repodir):
        cmd = ["git", "clone", self.clone_url, repodir]
        return run_cmd(cmd)

    def checkout(self, branch, repodir):
        cmd = ["git", "checkout", branch]
        return run_cmd(cmd, cwd=repodir)

    def render_rpkg_template(self):
        jinja_env = Environment(loader=FileSystemLoader("."))
        template = jinja_env.get_template("rpkg.conf.j2")
        parse = urlparse(self.clone_url)
        distgit_domain = parse.netloc
        return template.render(distgit_domain=distgit_domain, scheme=parse.scheme)

    def module_name(self, url):
        parse = urlparse(url)
        return re.sub(".git$", "", re.sub("^/c?git/", "", parse.path))

    def produce_srpm(self, config, module_name, repodir):
        cmd = ["rpkg", "--config", config, "--module-name", module_name, "srpm"]
        return run_cmd(cmd, cwd=repodir)

    @property
    def srpm(self):
        repodir = os.path.join(self.workdir, "repo")
        dest_files = os.listdir(repodir)
        dest_srpms = filter(lambda f: f.endswith(".src.rpm"), dest_files)

        if len(dest_srpms) != 1:
            log.debug("tmp_dest: {}".format(repodir))
            log.debug("dest_files: {}".format(dest_files))
            log.debug("dest_srpms: {}".format(dest_srpms))
            raise RuntimeError("No srpm files were generated.")
        return os.path.join(repodir, dest_srpms[0])


class MockBuilder(object):
    def __init__(self, task, srpm, resultdir=None):
        self.srpm = srpm
        self.task_id = task["task_id"]
        self.chroot = task["chroot"]
        self.buildroot_pkgs = task["buildroot_pkgs"]
        self.enable_net = task["enable_net"]
        self.repos = None
        self.use_bootstrap_container = None
        self.pkg_manager_conf = "dnf"
        self.resultdir = resultdir

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
        jinja_env = Environment(loader=FileSystemLoader("."))
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

    config = ConfigParser.RawConfigParser()
    config.readfp(open(args.config or "main.ini"))

    init(args,config)
    action = build_srpm if args.srpm else build_rpm
    action(args, config)


def init(args, config):
    resultdir = config.get("main", "resultdir")
    if os.path.exists(resultdir):
        shutil.rmtree(resultdir)
    os.makedirs(resultdir)


def build_srpm(args, config):
    task = get_task("/get-build-task/", args.task_id, config)

    # @TODO Select the provider based on source_type
    workdir = tempfile.mkdtemp()
    provider = DistGitProvider(task["source_json"], workdir)
    provider.run()
    shutil.copy2(provider.srpm, config.get("main", "resultdir"))


def build_rpm(args, config):
    task = get_task("/get-srpm-build-task/", args.task_id, config)

    workdir = tempfile.mkdtemp()
    provider = DistGitProvider(task["source_json"], workdir)
    provider.run()

    resultdir = config.get("main", "resultdir")
    builder = MockBuilder(task, provider.srpm, resultdir=resultdir)
    builder.run()
    builder.touch_success_file()


def get_task(endpoint, id, config):
    url = urljoin(urljoin(config.get("main", "frontend_url"), endpoint), id)
    response = requests.get(url)
    task = response.json()
    task["source_json"] = json.loads(task["source_json"])
    return task


if __name__ == "__main__":
    main()