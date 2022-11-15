import os
import logging
import shutil

from jinja2 import Environment, FileSystemLoader
from copr_rpmbuild import helpers
from .base import Provider
from ..helpers import CONF_DIRS


log = logging.getLogger("__main__")


class CustomProvider(Provider):
    chroot = 'fedora-rawhide-x86_64'
    builddeps = None
    repos = None
    file_script = None
    inner_resultdir = None
    inner_workdir = '/workdir'
    hook_payload_url = None

    workdir = None

    def init_provider(self):
        source_json = self.source_dict
        self.chroot = source_json.get('chroot')
        self.inner_resultdir = source_json.get('resultdir')
        self.builddeps = source_json.get('builddeps')
        self.repos = self.task.get('repos')
        self.timeout = source_json.get("timeout", 3600)

        if 'hook_data' in source_json:
            self.hook_payload_url = "{server}/tmp/{tmp}/hook_payload".format(
                server=self.config.get("main", "frontend_url"),
                tmp=source_json['tmp'],
            )

        self.file_script = os.path.join(self.workdir, 'script')
        with open(self.file_script, 'w') as script:
            script.write(source_json['script'])

    def render_mock_config_template(self, *_args):
        """
        Return a mock config (as a string) for a specific task
        """
        jinja_env = Environment(loader=FileSystemLoader(CONF_DIRS))
        template = jinja_env.get_template("mock-custom-build.cfg.j2")
        return template.render(
            chroot=self.chroot,
            repos=self.repos,
            macros=self.macros,
        )

    def produce_srpm(self):
        mock_config_file = self.generate_mock_config("mock-config.cfg")
        cmd = [
            'unbuffer',
            'copr-sources-custom',
            '--workdir', self.inner_workdir,
            '--mock-config', mock_config_file,
            '--script', self.file_script,
        ]
        if self.builddeps:
            cmd += ['--builddeps', self.builddeps]

        if self.hook_payload_url:
            chunk_size = 1024
            hook_payload_file = os.path.join(self.resultdir, 'hook_payload')
            response = self.request.get(self.hook_payload_url, stream=True)
            response.raise_for_status()

            with open(hook_payload_file, 'wb') as payload_file:
                for chunk in response.iter_content(chunk_size):
                    payload_file.write(chunk)

            cmd += ['--hook-payload-file', hook_payload_file]

        inner_resultdir = self.inner_workdir
        if self.inner_resultdir:
            # User wishes to re-define resultdir.
            cmd += ['--resultdir', self.inner_resultdir]
            inner_resultdir = os.path.normpath(os.path.join(
                self.inner_workdir, self.inner_resultdir))

        # prepare the sources
        process = helpers.GentlyTimeoutedPopen(cmd, timeout=self.timeout)
        try:
            process.communicate()
        except OSError as e:
            raise RuntimeError(str(e))
        finally:
            process.done()

        if process.returncode != 0:
            raise RuntimeError("Build failed")

        # copy the sources out into workdir
        mock = ['mock', '-r', mock_config_file]

        srpm_srcdir = os.path.join(self.workdir, 'srcdir')

        helpers.run_cmd(mock + ['--copyout', inner_resultdir, srpm_srcdir])
        helpers.run_cmd(mock + ['--scrub', 'all'])
        helpers.build_srpm(srpm_srcdir, self.resultdir)
        shutil.rmtree(srpm_srcdir)
