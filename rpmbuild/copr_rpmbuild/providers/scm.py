import os
import re
import logging
import munch
import shutil
import tarfile
import re

from copr_rpmbuild import helpers

from jinja2 import Environment, FileSystemLoader
from ..helpers import run_cmd, SourceType
from .base import Provider

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse


log = logging.getLogger("__main__")


class PackageContent(munch.Munch):
    """
    Class describing acquired package content.
    """
    def __init__(self, *args, **kwargs):
        self.spec_path = None
        self.source_paths = []
        self.extra_content = []
        super(PackageContent, self).__init__(*args, **kwargs)


class ScmProvider(Provider):
    def __init__(self, source_json, workdir=None, confdirs=None):
        super(ScmProvider, self).__init__(source_json, workdir, confdirs)
        if 'scm_url' in source_json: # Mock-SCM
            self.url = source_json.get('scm_url')
            self.subdir = source_json.get('scm_subdir')
            self.branch = source_json.get('scm_branch')
            self.scm_type = source_json.get('scm_type')
            self.spec_relpath = source_json.get('spec')
            self.test = True
            self.prepare_test_spec = False
        else: # Git and Tito
            self.url = source_json.get('git_url')
            self.subdir = source_json.get('git_dir')
            self.branch = source_json.get('git_branch')
            self.scm_type = 'git'
            self.spec_relpath = None
            self.test = source_json.get('tito_test')
            self.prepare_test_spec = self.test

    @property
    def resultdir(self):
        return self.workdir

    @resultdir.setter
    def resultdir(self, value):
        pass

    def run(self):
        content = self.get_content()
        log.info(content)

        cfg = self.render_rpkg_template()
        log.info(cfg)

        config_path = os.path.join(self.workdir, "rpkg.conf")
        f = open(config_path, "w+")
        f.write(cfg)
        f.close()

        self.touch_sources()
        result = self.produce_srpm(config_path)
        log.info(result)

    def render_rpkg_template(self):
        jinja_env = Environment(loader=FileSystemLoader(self.confdirs))
        template = jinja_env.get_template("rpkg.conf.j2")
        parse = urlparse(self.url)
        distgit_domain = parse.netloc
        return template.render(distgit_domain=distgit_domain, scheme=parse.scheme)

    def produce_srpm(self, config):
        cmd = ["rpkg", "--config", config, "srpm"]
        return run_cmd(cmd, cwd=self.workdir)

    def locate_spec(self, repo_subpath):
        if self.spec_relpath:
            spec_path = os.path.join(repo_subpath, self.spec_relpath)
        else:
            spec_path = helpers.locate_spec(repo_subpath)

        if not os.path.exists(spec_path):
            raise PackageImportException("Can't find spec file at {}".format(spec_path))

        return spec_path

    def clone_sources(self, repo_path):
        if self.scm_type == 'git':
            clone_cmd = ['git', 'clone', self.url, repo_path,
                   '--depth', '100', '--branch', self.branch or 'master']
        else:
            clone_cmd = ['git', 'svn', 'clone', self.url, repo_path,
                   '--branch', self.branch or 'master']

        helpers.run_cmd(clone_cmd)

    def checkout_sources(self, repo_path, commit_id):
        helpers.run_cmd(['git', '-C', repo_path, 'checkout', commit_id])

    def pack_sources(self, dir_to_pack, target_path, spec_info):
        tardir_name = spec_info.name + '-' + spec_info.version
        tardir_path = os.path.join(self.workdir, tardir_name)

        log.debug("Packing {} as {} into {}...".format(
            dir_to_pack, tardir_name, target_path))

        def exclude_vcs(tar_info):
            exclude_pattern = r'(/.git$|/.git/|/.gitignore$)'
            if re.search(exclude_pattern, tar_info.name):
                log.debug("Excluding {}".format(tar_info.name))
                return None
            return tar_info

        tarball = tarfile.open(target_path, 'w:gz')
        tarball.add(dir_to_pack, tardir_name, filter=exclude_vcs)
        tarball.close()

    def prepare_sources(self, repo_subpath, spec_path):
        spec_info = helpers.get_rpm_spec_info(spec_path)
        source_paths = []
        extra_content = []
        source_zero = None
        downstream_repo = False

        for (path, num, flags) in spec_info.sources:
            filename = os.path.basename(path)

            if num == 0 and flags == 1:
                source_zero = filename

            orig_path = os.path.join(repo_subpath, filename)
            if not os.path.isfile(orig_path):
                continue

            downstream_repo = True

            target_path = os.path.join(self.workdir, filename)
            shutil.copy(orig_path, target_path)

            if flags == 1:
                source_paths.append(target_path)
            else:
                extra_content.append(target_path)

        include = lambda f: not re.search(r'(^README|.spec$|^\.|tito.props)', f)
        if not list(filter(include, os.listdir(repo_subpath))):
            downstream_repo = True

        if not downstream_repo and source_zero:
            target_path = os.path.join(self.workdir, source_zero)
            self.pack_sources(repo_subpath, target_path, spec_info)
            source_paths.append(target_path)

        return (source_paths, extra_content)

    def get_content(self):
        repo_path = os.path.join(self.workdir, os.path.basename(self.url))
        self.clone_sources(repo_path)

        if self.subdir:
            repo_subpath = os.path.join(repo_path, self.subdir)
        else:
            repo_subpath = repo_path

        head_spec_path = self.locate_spec(repo_subpath)
        package_name = helpers.get_package_name(head_spec_path)

        if self.test:
            target_commit_id = 'HEAD'
        else:
            target_commit_id = helpers.get_latest_package_tag(package_name, repo_path) or 'HEAD'

        self.checkout_sources(repo_path, target_commit_id)
        orig_spec_path = self.locate_spec(repo_subpath)

        spec_path = os.path.join(
            self.workdir, os.path.basename(orig_spec_path))

        if self.prepare_test_spec:
            helpers.prepare_test_spec(
                orig_spec_path, spec_path, repo_path, package_name)
        else:
            shutil.copy(orig_spec_path, spec_path)

        source_paths, extra_content = self.prepare_sources(repo_subpath, spec_path)

        return PackageContent(
            spec_path=spec_path,
            source_paths=source_paths,
            extra_content=extra_content)
