import os
import logging
import shutil

from copr_rpmbuild import helpers
from .base import Provider


log = logging.getLogger("__main__")


class CustomProvider(Provider):
    chroot = 'fedora-rawhide-x86_64'
    builddeps = None
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
        self.timeout = source_json.get("timeout", 3600)

        if 'hook_data' in source_json:
            self.hook_payload_url = "{server}/tmp/{tmp}/hook_payload".format(
                server=self.config.get("main", "frontend_url"),
                tmp=source_json['tmp'],
            )

        self.file_script = os.path.join(self.workdir, 'script')
        with open(self.file_script, 'w') as script:
            script.write(source_json['script'])


    def produce_srpm(self):
        mock_config_file = os.path.join(self.resultdir, 'mock-config.cfg')

        with open(mock_config_file, 'w') as f:
            # Enable network.
            f.write("include('/etc/mock/{0}.cfg')\n".format(self.chroot))
            f.write("config_opts['rpmbuild_networking'] = True\n")
            f.write("config_opts['use_host_resolv'] = True\n")
            # Important e.g. to keep '/script' file available across several
            # /bin/mock calls (when tmpfs_enable is on).
            f.write("config_opts['plugin_conf']['tmpfs_opts']['keep_mounted'] = True\n")

            for key, value in self.macros.items():
                f.write("config_opts['macros']['{0}'] = '{1}'\n"
                        .format(key, value))

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
