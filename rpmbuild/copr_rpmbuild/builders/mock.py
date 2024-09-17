import re
import os
import sys
import logging
import shutil
import subprocess

from jinja2 import Environment, FileSystemLoader
from copr_rpmbuild.config import Config
from copr_rpmbuild.helpers import (
    locate_spec,
    CONF_DIRS,
    get_mock_uniqueext,
    GentlyTimeoutedPopen,
    macros_for_task,
    mock_snippet_for_tags,
)

log = logging.getLogger("__main__")

MOCK_CALL = ['unbuffer', 'mock']

class MockBuilder(object):
    def __init__(self, task, sourcedir, resultdir, config):
        self.task_id = task.get("task_id")
        self.build_id = re.sub("-.*", "", self.task_id)
        self.chroot = task.get("chroot")
        self.buildroot_pkgs = task.get("buildroot_pkgs")
        self.enable_net = task.get("enable_net")
        self.repos = task.get("repos")
        self.bootstrap = task.get("bootstrap")
        self.bootstrap_image = task.get("bootstrap_image")
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
        self.isolation = task.get("isolation")
        self.macros = macros_for_task(task, config)
        self.uniqueext = get_mock_uniqueext()
        self.allow_user_ssh = task.get("allow_user_ssh")
        self.tags = task.get("tags", [])

        self.copr_rpmbuild_config = Config()
        self.copr_rpmbuild_config.load_config()

    def run(self):
        open(self.logfile, 'w').close() # truncate logfile
        self.prepare_configs()

        spec = locate_spec(self.sourcedir)
        shutil.copy(spec, self.resultdir)
        try:
            self.produce_rpm(spec, self.sourcedir, self.resultdir)
        finally:
            self.mock_clean()

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
        return template.render(
            chroot=self.chroot,
            buildroot_pkgs=self.buildroot_pkgs,
            enable_net=self.enable_net,
            bootstrap=self.bootstrap,
            bootstrap_image=self.bootstrap_image,
            repos=self.repos,
            modules=self.module_setup_commands,
            copr_build_id=self.build_id,
            isolation=self.isolation,
            macros=self.macros,
            mock_snippet=mock_snippet_for_tags(
                self.copr_rpmbuild_config.tags_to_mock_snippet, self.tags
            ),
        )

    def produce_srpm(self, spec, sources, resultdir):
        cmd = MOCK_CALL + [
            "--buildsrpm",
            "--spec", spec,
            "--sources", sources,
            "--resultdir", resultdir,
            "--uniqueext", self.uniqueext,
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

    def mock_clean(self):
        """ Do a best effort Mock cleanup. """
        if self.allow_user_ssh:
            return

        cmd = MOCK_CALL + [
            "-r", self.mock_config_file,
            "--uniqueext", self.uniqueext,
            "--scrub", "bootstrap",
            "--scrub", "chroot",
            "--scrub", "root-cache",
            "--quiet",
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
    def module_setup_commands(self):
        """ Return the list() of modules to be enabled """
        tuples  = []
        if self.modules is None:
            return tuples

        assert isinstance(self.modules, dict)
        assert 'toggle' in self.modules
        assert isinstance(self.modules['toggle'], list)
        assert self.modules['toggle']

        for toggle in self.modules['toggle']:
            assert isinstance(toggle, dict)
            # The toggle dict should always basically be a tuple of two items
            assert len(toggle) == 1
            command, module = toggle.popitem()
            # we only have 'enable' and 'disable' now
            assert command in ["enable", "disable"]
            assert isinstance(module, str)
            tuples.append((command, module))

        return tuples

    def produce_rpm(self, spec, sources, resultdir):
        cmd = MOCK_CALL + [
               "--spec", spec,
               "--sources", sources,
               "--resultdir", resultdir,
               "--uniqueext", self.uniqueext,
               "-r", self.mock_config_file]

        for with_opt in self.with_opts:
            cmd += ["--with", with_opt]

        for without_opt in self.without_opts:
            cmd += ["--without", without_opt]

        # This is safe because builds that allow user SSH access are run in
        # a separate sandbox which is not shared with any other build (not even
        # from the same user)
        if self.allow_user_ssh:
            cmd += ["--no-cleanup-after"]

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
