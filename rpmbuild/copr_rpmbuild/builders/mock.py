import os
import sys
import logging
import shutil
import subprocess

from jinja2 import Environment, FileSystemLoader
from ..helpers import locate_spec, locate_srpm, CONF_DIRS, get_mock_uniqueext

log = logging.getLogger("__main__")


class MockBuilder(object):
    def __init__(self, task, sourcedir, resultdir, config):
        self.task_id = task.get("task_id")
        self.chroot = task.get("chroot")
        self.buildroot_pkgs = task.get("buildroot_pkgs")
        self.enable_net = task.get("enable_net")
        self.repos = task.get("repos")
        self.use_bootstrap_container = task.get("use_bootstrap_container")
        self.pkg_manager_conf = "dnf" if "custom-1" in task.get("chroot") else "yum"
        self.timeout = task.get("timeout", 3600)
        self.with_opts = task.get("with_opts", [])
        self.without_opts = task.get("without_opts", [])
        self.sourcedir = sourcedir
        self.resultdir = resultdir
        self.config = config
        self.logfile = self.config.get("main", "logfile")

    def run(self):
        open(self.logfile, 'w').close() # truncate logfile
        configdir = os.path.join(self.resultdir, "configs")
        self.prepare_configs(configdir)

        spec = locate_spec(self.sourcedir)
        shutil.copy(spec, self.resultdir)
        self.produce_srpm(spec, self.sourcedir, configdir, self.resultdir)

        srpm = locate_srpm(self.resultdir)
        self.produce_rpm(srpm, configdir, self.resultdir)

    def prepare_configs(self, configdir):
        site_config_path = os.path.join(configdir, "site-defaults.cfg")
        mock_config_path = os.path.join(configdir, "{0}.cfg".format(self.chroot))
        child_config_path = os.path.join(configdir, "child.cfg")

        try:
            os.makedirs(configdir)
        except OSError:
            pass

        shutil.copy2("/etc/mock/site-defaults.cfg", site_config_path)
        shutil.copy2("/etc/mock/{0}.cfg".format(self.chroot), mock_config_path)
        cfg = self.render_config_template()
        with open(child_config_path, "w") as child:
            child.write(cfg)

        return [child_config_path, mock_config_path, site_config_path]

    def render_config_template(self):
        jinja_env = Environment(loader=FileSystemLoader(CONF_DIRS))
        template = jinja_env.get_template("mock.cfg.j2")
        return template.render(chroot=self.chroot, task_id=self.task_id, buildroot_pkgs=self.buildroot_pkgs,
                               enable_net=self.enable_net, use_bootstrap_container=self.use_bootstrap_container,
                               repos=self.repos, pkg_manager_conf=self.pkg_manager_conf)

    def produce_srpm(self, spec, sources, configdir, resultdir):
        cmd = [
            "unbuffer", "/usr/bin/mock",
            "--buildsrpm",
            "--spec", spec,
            "--sources", sources,
            "--configdir", configdir,
            "--resultdir", resultdir,
            "--define", "%_disable_source_fetch 0",
            "--uniqueext", get_mock_uniqueext(),
            "-r", "child"]

        for with_opt in self.with_opts:
            cmd += ["--with", with_opt]

        for without_opt in self.without_opts:
            cmd += ["--without", without_opt]

        process = GentlyTimeoutedPopen(cmd, stdin=subprocess.PIPE,
                timeout=self.timeout)

        try:
            process.communicate()
        except OSError as e:
            raise RuntimeError(str(e))
        finally:
            process.done()

        if process.returncode != 0:
            raise RuntimeError("Build failed")


    def produce_rpm(self, srpm, configdir, resultdir):
        cmd = ["unbuffer", "/usr/bin/mock",
               "--rebuild", srpm,
               "--configdir", configdir,
               "--resultdir", resultdir,
               "--uniqueext", get_mock_uniqueext(),
               "-r", "child"]

        for with_opt in self.with_opts:
            cmd += ["--with", with_opt]

        for without_opt in self.without_opts:
            cmd += ["--without", without_opt]

        process = GentlyTimeoutedPopen(cmd, stdin=subprocess.PIPE,
                timeout=self.timeout)

        try:
            process.communicate()
        except OSError as e:
            raise RuntimeError(str(e))
        finally:
            process.done()

        if process.returncode != 0:
            raise RuntimeError("Build failed")

    def touch_success_file(self):
        with open(os.path.join(self.resultdir, "success"), "w") as success:
            success.write("done")
