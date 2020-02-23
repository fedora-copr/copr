import os
import sys
import logging
import shutil
import subprocess

from jinja2 import Environment, FileSystemLoader
from ..helpers import locate_spec, locate_srpm, CONF_DIRS, get_mock_uniqueext, GentlyTimeoutedPopen

log = logging.getLogger("__main__")

MOCK_CALL = ['unbuffer', 'mock']

class MockBuilder(object):
    def __init__(self, task, sourcedir, resultdir, config):
        self.task_id = task.get("task_id")
        self.chroot = task.get("chroot")
        self.buildroot_pkgs = task.get("buildroot_pkgs")
        self.enable_net = task.get("enable_net")
        self.repos = task.get("repos")
        self.use_bootstrap_container = task.get("use_bootstrap_container")
        self.timeout = task.get("timeout", 3600)
        self.with_opts = task.get("with_opts", [])
        self.without_opts = task.get("without_opts", [])
        self.sourcedir = sourcedir
        self.resultdir = resultdir
        self.config = config
        self.logfile = self.config.get("main", "logfile")
        self.copr_username = task.get("project_owner")
        self.copr_projectname = task.get("project_name")
        self.modules = task.get("modules")

    def run(self):
        open(self.logfile, 'w').close() # truncate logfile
        self.prepare_configs()

        spec = locate_spec(self.sourcedir)
        shutil.copy(spec, self.resultdir)
        try:
            self.produce_srpm(spec, self.sourcedir, self.resultdir)

            srpm = locate_srpm(self.resultdir)
            self.produce_rpm(srpm, self.resultdir)
        finally:
            self.clean_cache()
            self.archive_configs()

    def prepare_configs(self):
        try:
            os.makedirs(self.configdir)
        except OSError:
            pass

        # Copy all the host's configuration files for the reproducibility
        # purposes (documentation), those files are not used for builds.
        subprocess.call(['rsync', '-rl', '/etc/mock/', self.configdir])

        # Generate the target mock config file.
        with open(self.mock_config_file, "w") as child:
            child.write(self.render_config_template())

    def render_config_template(self):
        jinja_env = Environment(loader=FileSystemLoader(CONF_DIRS))
        template = jinja_env.get_template("mock.cfg.j2")
        return template.render(chroot=self.chroot, task_id=self.task_id, buildroot_pkgs=self.buildroot_pkgs,
                               enable_net=self.enable_net, use_bootstrap_container=self.use_bootstrap_container,
                               repos=self.repos,
                               copr_username=self.copr_username, copr_projectname=self.copr_projectname,
                               modules=self.enable_modules)

    def produce_srpm(self, spec, sources, resultdir):
        cmd = MOCK_CALL + [
            "--buildsrpm",
            "--spec", spec,
            "--sources", sources,
            "--resultdir", resultdir,
            "--uniqueext", get_mock_uniqueext(),
            "-r", self.mock_config_file]

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
            raise RuntimeError("Mock build failed")

    def clean_cache(self):
        """ Do best effort /var/mock/cache cleanup. """
        cmd = MOCK_CALL + [
            "-r", self.mock_config_file,
            "--scrub", "cache", "--quiet",
        ]
        subprocess.call(cmd) # ignore failure here, if any

    def archive_configs(self):
        subprocess.call(['tar', '-cz', '--remove-files',
                         '-C', os.path.dirname(self.configdir),
                         '-f', os.path.join(self.resultdir, 'configs.tar.gz'),
                         os.path.basename(self.configdir)])

    @property
    def configdir(self):
        return os.path.join(self.resultdir, "configs")

    @property
    def mock_config_file(self):
        return os.path.join(self.configdir, "child.cfg")

    @property
    def enable_modules(self):
        """ Return the list() of modules to be enabled """
        enable = []
        if self.modules is None:
            return enable

        assert isinstance(self.modules, dict)
        assert 'toggle' in self.modules
        assert isinstance(self.modules['toggle'], list)
        assert self.modules['toggle']

        for toggle in self.modules['toggle']:
            assert isinstance(toggle, dict)
            # we only have 'enable' now
            assert 'enable' in toggle
            assert isinstance(toggle['enable'], str)
            module = toggle['enable'].strip()
            enable.append(module)

        return enable

    def produce_rpm(self, srpm, resultdir):
        cmd = MOCK_CALL + [
               "--rebuild", srpm,
               "--resultdir", resultdir,
               "--uniqueext", get_mock_uniqueext(),
               "-r", self.mock_config_file]

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
