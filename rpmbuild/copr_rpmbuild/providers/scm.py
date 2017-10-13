import os
import re
import logging
import munch
import shutil
import tarfile
import re
import tempfile

from copr_rpmbuild import helpers

from jinja2 import Environment, FileSystemLoader
from ..helpers import run_cmd, SourceType, CONF_DIRS
from .base import Provider

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

log = logging.getLogger("__main__")


class ScmProvider(Provider):
    def __init__(self, source_json, outdir, config):
        super(ScmProvider, self).__init__(source_json, outdir, config)
        if 'scm_url' in source_json: # Mock-SCM
            self.clone_url = source_json.get('scm_url')
            self.repo_subdir = source_json.get('scm_subdir', '')
            self.committish = source_json.get('scm_branch')
            self.scm_type = source_json.get('scm_type')
            self.spec_relpath = source_json.get('spec', '')
            self.test = True
            self.prepare_test_spec = False
            self.srpm_build_method = source_json.get('srpm_method') or 'rpkg'
        elif 'git_url' in source_json: # Git and Tito
            self.clone_url = source_json.get('git_url')
            self.repo_subdir = source_json.get('git_dir', '')
            self.committish = source_json.get('git_branch')
            self.scm_type = 'git'
            self.spec_relpath = None
            self.test = source_json.get('tito_test')
            self.prepare_test_spec = self.test
            self.srpm_build_method = source_json.get('srpm_method') or 'rpkg'
        else:
            self.clone_url = source_json.get('clone_url')
            self.committish = source_json.get('branch')
            self.srpm_build_method = 'rpkg'
            self.scm_type = 'git'
            self.repo_subdir = ''

        self.repo_dirname = os.path.splitext(os.path.basename(self.clone_url))[0]
        self.repo_path = os.path.join(self.workdir, self.repo_dirname)

    def run(self):
        result = self.produce_srpm(config_path)
        log.info(result)

    def generate_rpkg_config(self):
        clone_url_hostname = urlparse(self.clone_url).netloc
        found_config_section = None

        index = 0
        config_section = 'distgit{index}'.format(index=index)
        while self.config.has_section(config_section):
            distgit_hostname_pattern = self.config.get(
                config_section, 'distgit_hostname_pattern')
            if re.match(distgit_hostname_pattern, clone_url_hostname):
                found_config_section = config_section
                break
            index += 1
            config_section = 'distgit{index}'.format(index=index)

        if not found_config_section:
            return '/etc/rpkg.conf'

        distgit_lookaside_url = self.config.get(
            found_config_section, 'distgit_lookaside_url')
        distgit_clone_url = self.config.get(
            found_config_section, 'distgit_clone_url')

        jinja_env = Environment(loader=FileSystemLoader(CONF_DIRS))
        template = jinja_env.get_template("rpkg.conf.j2")
        config = template.render(lookaside_url=distgit_lookaside_url,
                                 clone_url=distgit_clone_url)
        log.debug(config+'\n')
        config_path = os.path.join(self.workdir, "rpkg.conf")

        f = open(config_path, "w+")
        f.write(config)
        f.close()

        return config_path

    def get_rpkg_command(self):
        return ['rpkg', '-C', self.generate_rpkg_config(), 'srpm',
                '--outdir', self.outdir] + (['--spec', self.spec_relpath]
                                            if self.spec_relpath else [])

    def get_tito_command(self):
        return ['tito', 'build', '--srpm', '--output', self.outdir]

    def get_tito_test_command(self):
        return ['tito', 'build', '--test', '--srpm', '--output', self.outdir]

    def get_make_srpm_command(self):
        mock_workdir = '/mnt' + self.workdir
        mock_outdir = '/mnt' + self.outdir
        mock_repodir = os.path.join(mock_workdir, self.repo_dirname)
        mock_cwd = os.path.join(mock_repodir, self.repo_subdir)

        mock_bind_mount_cmd_part = \
            '--plugin-option=bind_mount:dirs=(("{0}", "{1}"), ("{2}", "{3}"))'\
            .format(self.workdir, mock_workdir, self.outdir, mock_outdir)

        makefile_path = os.path.join(mock_repodir, '.copr', 'Makefile')
        make_srpm_cmd_part = \
            'cd {0}; make -f {1} srpm outdir="{2}" spec="{3}"'\
            .format(mock_cwd, makefile_path, mock_outdir, self.spec_relpath or '')

        return ['mock', '-r', '/etc/copr-rpmbuild/make_srpm_mock.cfg',
                mock_bind_mount_cmd_part, '--chroot', make_srpm_cmd_part]

    def produce_srpm(self):
        self.clone_and_checkout()
        cwd = os.path.join(self.repo_path, self.repo_subdir)
        cmd = {
            'rpkg': self.get_rpkg_command,
            'tito': self.get_tito_command,
            'tito_test': self.get_tito_test_command,
            'make_srpm': self.get_make_srpm_command,
        }[self.srpm_build_method]()
        return run_cmd(cmd, cwd=cwd)

    def produce_sources(self):
        self.clone_and_checkout()
        cwd = os.path.join(self.repo_path, self.repo_subdir)

        copy_cmd = ['cp', '-r', '.', self.outdir]
        run_cmd(copy_cmd, cwd=cwd)

        cmd = ['rpkg', '-C', self.generate_rpkg_config(),
               'sources', '--outdir', self.outdir]
        return run_cmd(cmd, cwd=cwd)

    def clone_and_checkout(self):
        if self.scm_type == 'git':
            clone_cmd = ['git', 'clone', self.clone_url,
                         self.repo_path, '--depth', '500',
                         '--no-single-branch']
        else:
            clone_cmd = ['git', 'svn', 'clone', self.clone_url,
                         self.repo_path]

        helpers.run_cmd(clone_cmd)

        checkout_cmd = ['git', 'checkout', self.committish]
        helpers.run_cmd(checkout_cmd, cwd=self.repo_path)
