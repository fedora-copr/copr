import os
import errno
import logging
import shutil
import stat
import tempfile
from jinja2 import Environment, FileSystemLoader

from copr_common.request import SafeRequest
from copr_rpmbuild.helpers import CONF_DIRS
from copr_rpmbuild.helpers import run_cmd


log = logging.getLogger("__main__")


class Provider(object):
    # pylint: disable=too-many-instance-attributes
    _safe_resultdir = None

    def __init__(self, source_dict, config, macros=None, task=None):
        self.source_dict = source_dict
        self.config = config
        self.request = SafeRequest(log=log)
        self.task = task

        # Additional macros that should be defined in the buildroot
        self.macros = macros or {}

        # Where we should produce output, everything there gets copied to
        # backend once build ends!
        self.real_resultdir = config.get("main", "resultdir")

        # When True, we don't consider the method safe enough to put the results
        # directly to self.real_resultdir.  So we first put the results below
        # the self._safe_resultdir.  Note that this may mean that everything
        # (perhaps large uploaded source RPMs) could end-up in the storage
        # twice, therefore try to keep it False if possible.
        self.use_safe_resultdir = False

        # Where we can create the temporary directories.  These are
        # automatically removed when possible when build ends.
        self.workspace = config.get("main", "workspace")

        # A per-task uniquely named working directory.  Ideally all the
        # work-in-progress stuff should live here.
        self.workdir = tempfile.mkdtemp(dir=self.workspace, prefix="workdir-")
        try:
            os.mkdir(self.workdir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # Change home directory to workdir and create .rpmmacros there
        os.environ["HOME"] = self.workdir
        self.create_rpmmacros()
        self.init_provider()

    def init_provider(self):
        """
        Additional configuration stuff specific to a concrete provider.
        Automatically called by __init__(), and it is _optional_, therefore we
        don't raise NotImplementedError in Provider.init_provider() parent.
        """

    @property
    def resultdir(self):
        """
        Create a sub-directory (on demand, when accessed) with permissive
        permissions to allow user-namespaces (e.g. systemd-nspawn) doing
        permissions/ownership changes on the files there.
        """
        if not self.use_safe_resultdir:
            return self.real_resultdir

        if not self._safe_resultdir:
            self._safe_resultdir = tempfile.mkdtemp(dir=self.workspace,
                                                    prefix="safe-resultdir-")

            # allow namespaces (even root) to give the files away
            for directory in [self.workdir, self._safe_resultdir]:
                os.chmod(directory, stat.S_IRWXU|stat.S_IRWXO)

        return self._safe_resultdir

    def copy_insecure_results(self):
        """
        Copy the possibly non-removable results to real_resultdir, that will be
        picked-up by copr-backend.
        """
        if not self._safe_resultdir:
            return
        shutil.copytree(self._safe_resultdir, self.real_resultdir,
                        dirs_exist_ok=True)

    @staticmethod
    def _best_effort_cleanup(directory):
        try:
            shutil.rmtree(directory)
        except IOError:
            log.error("Can not remove the '%s', run copr-builder-cleanup.",
                      directory)

    def cleanup(self):
        """ Best effort cleanup of the working directories """
        self._best_effort_cleanup(self.workdir)
        if self._safe_resultdir:
            self._best_effort_cleanup(self._safe_resultdir)

    def create_rpmmacros(self):
        path = os.path.join(self.workdir, ".rpmmacros")
        with open(path, "w") as rpmmacros:
            for key, value in self.macros.items():
                rpmmacros.write("{0} {1}\n".format(key, value))

    def generate_mock_config(self, config_name=None):
        """
        Generate a mock config file for a specific task
        """
        config_name = config_name or "mock-source-build.cfg"
        template_name = config_name + ".j2"
        mock_config_file = os.path.join(self.resultdir, config_name)
        with open(mock_config_file, "w") as fd:
            fd.write(self.render_mock_config_template(template_name))
        return mock_config_file

    def render_mock_config_template(self, template_name):
        """
        Return a mock config (as a string) for a specific task
        """
        jinja_env = Environment(loader=FileSystemLoader(CONF_DIRS))
        template = jinja_env.get_template(template_name)
        return template.render(macros=self.macros)

    def produce_srpm(self):
        """
        Using the TASK dict and the CONFIG, generate a source RPM in the
        RESULTDIR.  Each method needs to override this one.
        """
        raise NotImplementedError

    def build_srpm_from_spec(self, spec_path):
        """
        Generate a SRPM package for a locally stored spec file
        """
        mock_config_file = self.generate_mock_config()
        cmd = ["mock", "-r", mock_config_file,
               "--buildsrpm", "--spec", spec_path,
               "--resultdir", self.resultdir]

        for key, value in self.macros.items():
            cmd += ["--define", "{0} {1}".format(key, value)]

        return run_cmd(cmd, cwd=self.workdir)
