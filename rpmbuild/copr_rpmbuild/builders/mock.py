import os
import sys
import logging
import shutil
import subprocess
from jinja2 import Environment, FileSystemLoader
from ..helpers import run_cmd

log = logging.getLogger("__main__")


class MockBuilder(object):
    def __init__(self, task, srpm, logfile=None, resultdir=None, confdirs=None):
        self.srpm = srpm
        self.task_id = task["task_id"]
        self.chroot = task["chroot"]
        self.buildroot_pkgs = task["buildroot_pkgs"]
        self.enable_net = task["enable_net"]
        self.repos = task["repos"]
        self.use_bootstrap_container = task["use_bootstrap_container"]
        self.pkg_manager_conf = "dnf" if "custom-1" in task["chroot"] else "yum"
        self.resultdir = resultdir
        self.confdirs = confdirs
        self.logfile = logfile
        log.info(self.__dict__)

    def run(self):
        configdir = os.path.join(self.resultdir, "configs")
        os.makedirs(configdir)
        shutil.copy2("/etc/mock/site-defaults.cfg", configdir)
        shutil.copy2("/etc/mock/{0}.cfg".format(self.chroot), configdir)
        cfg = self.render_config_template()
        with open(os.path.join(configdir, "child.cfg"), "w") as child:
            child.write(cfg)

        self.produce_rpm(self.srpm, configdir, self.resultdir)

    def render_config_template(self):
        jinja_env = Environment(loader=FileSystemLoader(self.confdirs))
        template = jinja_env.get_template("mock.cfg.j2")
        return template.render(chroot=self.chroot, task_id=self.task_id, buildroot_pkgs=self.buildroot_pkgs,
                               enable_net=self.enable_net, use_bootstrap_container=self.use_bootstrap_container,
                               repos=self.repos, pkg_manager_conf=self.pkg_manager_conf)

    def produce_rpm(self, srpm, configdir, resultdir):
        cmd = ["unbuffer", "/usr/bin/mock",
               "--rebuild", srpm,
               "--configdir", configdir,
               "--resultdir", resultdir,
               "-r", "child"]

        log.info(' '.join(cmd))

        def preexec_fn():
            if not self.logfile:
                return
            cmd = "tee {}".format(self.logfile)
            tee = subprocess.Popen(cmd, stdin=subprocess.PIPE, shell=True)
            os.dup2(tee.stdin.fileno(), sys.stdout.fileno())
            os.dup2(tee.stdin.fileno(), sys.stderr.fileno())

        process = subprocess.Popen(
            cmd, stdin=subprocess.PIPE, preexec_fn=preexec_fn)

        try:
            process.communicate()
        except OSError as e:
            raise RuntimeError(str(e))

        if process.returncode != 0:
            raise RuntimeError("Build failed")


    def touch_success_file(self):
        with open(os.path.join(self.resultdir, "success"), "w") as success:
            success.write("done")
