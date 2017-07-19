# coding: utf-8

import munch
import logging
import tempfile
import shutil
import glob
import os
import rpm
import tarfile
import re
import subprocess
from jinja2 import Environment,FileSystemLoader

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from exceptions import PackageImportException

import helpers

log = logging.getLogger(__name__)


class SourceType:
    LINK = 1
    UPLOAD = 2
    GIT_AND_TITO = 3
    MOCK_SCM = 4
    PYPI = 5
    RUBYGEMS = 6
    DISTGIT = 7


class PackageContent(munch.Munch):
    """
    Class describing acquired package content.
    """
    def __init__(self, *args, **kwargs):
        self.spec_path = None
        self.source_paths = []
        self.extra_content = []
        super(PackageContent, self).__init__(*args, **kwargs)


class PackageContentProviderFactory(object):
    """
    Proxy to instantiate appropriate SourceProvider child
    for a given import task.
    """

    @classmethod
    def getInstance(self, task, opts):
        try:
            if (task.source_type == SourceType.LINK or
                    task.source_type == SourceType.UPLOAD):
                if task.source_data['url'].endswith('.spec'):
                    provider_class = SpecUrlProvider
                else:
                    provider_class = SrpmUrlProvider
            elif task.source_type == SourceType.GIT_AND_TITO:
                provider_class = ScmProvider
            elif task.source_type == SourceType.MOCK_SCM:
                provider_class = ScmProvider
            elif task.source_type == SourceType.PYPI:
                provider_class = PyPIProvider
            elif task.source_type == SourceType.RUBYGEMS:
                provider_class = RubyGemsProvider
            elif task.source_type == SourceType.DISTGIT:
                provider_class = DistGitProvider
        except KeyError as e:
            raise PackageImportException(str(e))

        if not provider_class:
            raise PackageImportException(
                "Got unknown source type: {}".format(task.source_type)
            )

        return provider_class(opts)


class PackageContentProvider(object):
    """
    Base class for downloading upstream sources and
    transforming them into (spec, patches, sources) triplet.
    """
    def __init__(self, opts):
        self.opts = opts
        self.workdir = tempfile.mkdtemp()
        self.dirs_to_cleanup = [self.workdir]

    def get_content(self, task):
        """
        This is the main method that a child should
        provide.

        :return PackageContent
        """
        raise NotImplemented()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()

    def cleanup(self):
        for directory in self.dirs_to_cleanup:
            try:
                shutil.rmtree(directory)
            except OSError as e:
                pass #what else we can do? Hopefuly tmpreaper will clean it up
        self.dirs_to_cleanup = []


class ScmProvider(PackageContentProvider):
    def get_config(self, task):
        """A compatibility method that converts
        old source_data format for Tito and MockSCM
        methods into new universal one. This is a hopefully a
        temporary solution to fix the original design.
        GIT_AND_TITO and MOCK_SCM "sources" will be deprecated
        and replaced by actual package content sources: GIT,
        SVN, ..., or just one: SCM.
        """
        scm_config = munch.Munch()

        if task.source_type == SourceType.GIT_AND_TITO:
            scm_config.url = task.source_data.get('git_url')
            scm_config.subdir = task.source_data.get('git_dir')
            scm_config.branch = task.source_data.get('git_branch')
            scm_config.scm_type = 'git'
            scm_config.spec_relpath = None
            scm_config.test = task.source_data.get('tito_test')
            scm_config.prepare_test_spec = scm_config.test
        elif task.source_type == SourceType.MOCK_SCM:
            scm_config.url = task.source_data.get('scm_url')
            scm_config.subdir = task.source_data.get('scm_subdir')
            scm_config.branch = task.source_data.get('scm_branch')
            scm_config.scm_type = task.source_data.get('scm_type')
            scm_config.spec_relpath = task.source_data.get('spec')
            scm_config.test = True
            scm_config.prepare_test_spec = False
        else:
            raise PackageImportException("Incorrect scm_type for ScmProvider.")

        return scm_config

    def locate_spec(self, scm_config, repo_subpath):
        if scm_config.spec_relpath:
            spec_path = os.path.join(repo_subpath, scm_config.spec_relpath)
        else:
            spec_path = helpers.locate_spec(repo_subpath)

        if not os.path.exists(spec_path):
            raise PackageImportException("Can't find spec file at {}".format(spec_path))

        return spec_path

    def clone_sources(self, scm_config, repo_path):
        if scm_config.scm_type == 'git':
            clone_cmd = ['git', 'clone', scm_config.url, repo_path,
                   '--depth', '100', '--branch', scm_config.branch or 'master']
        else:
            clone_cmd = ['git', 'svn', 'clone', scm_config.url, repo_path,
                   '--branch', scm_config.branch or 'master']

        helpers.run_cmd(clone_cmd)

    def checkout_sources(self, scm_config, repo_path, commit_id):
        helpers.run_cmd(['git', '-C', repo_path, 'checkout', commit_id])

    def pack_sources(self, dir_to_pack, target_path, spec_info):
        tardir_name = spec_info.name + '-' + spec_info.version
        tardir_path = os.path.join(self.workdir, tardir_name)

        log.debug("Packing {} as {} into {}...".format(
            dir_to_pack, tardir_name, target_path))

        def exclude_vcs(tar_info):
            exclude_pattern = r'(/.git|/.gitignore)'
            if re.search(exclude_pattern, tar_info.name):
                log.debug("Excluding {}".format(tar_info.name))
                return None
            return tar_info

        tarball = tarfile.open(target_path, 'w:gz')
        tarball.add(dir_to_pack, tardir_name, filter=exclude_vcs)
        tarball.close()

    def prepare_sources(self, scm_config, repo_subpath, spec_path):
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

        include = lambda f: not re.search('(^README|.spec$|^\.|tito.props)', f)
        if not filter(include, os.listdir(repo_subpath)):
            downstream_repo = True

        if not downstream_repo and source_zero:
            target_path = os.path.join(self.workdir, source_zero)
            self.pack_sources(repo_subpath, target_path, spec_info)
            source_paths.append(target_path)

        return (source_paths, extra_content)

    def get_content(self, task):
        scm_config = self.get_config(task)
        repo_path = os.path.join(self.workdir, os.path.basename(scm_config.url))
        self.clone_sources(scm_config, repo_path)

        if scm_config.subdir:
            repo_subpath = os.path.join(repo_path, scm_config.subdir)
        else:
            repo_subpath = repo_path

        head_spec_path = self.locate_spec(scm_config, repo_subpath)
        package_name = helpers.get_package_name(head_spec_path)

        if scm_config.test:
            target_commit_id = 'HEAD'
        else:
            target_commit_id = helpers.get_latest_package_tag(package_name, repo_path) or 'HEAD'

        self.checkout_sources(scm_config, repo_path, target_commit_id)
        orig_spec_path = self.locate_spec(scm_config, repo_subpath)

        spec_path = os.path.join(
            self.workdir, os.path.basename(orig_spec_path))

        if scm_config.prepare_test_spec:
            helpers.prepare_test_spec(
                orig_spec_path, spec_path, repo_path, package_name)
        else:
            shutil.copy(orig_spec_path, spec_path)

        source_paths, extra_content = self.prepare_sources(
            scm_config, repo_subpath, spec_path)

        return PackageContent(
            spec_path=spec_path,
            source_paths=source_paths,
            extra_content=extra_content)


class PyPIProvider(PackageContentProvider):
    def get_content(self, task):
        cmd = ['pyp2rpm', task.source_data['pypi_package_name'], '-s', '-d', self.workdir]

        for i, python_version in \
                enumerate(task.source_data.get('python_versions', [])):
            if i == 0:
                cmd += ['-b', str(python_version)]
            else:
                cmd += ['-p', str(python_version)]

        if 'pypi_package_version' in task.source_data:
            cmd += ['-v', task.source_data['pypi_package_version']]

        result = helpers.run_cmd(cmd)

        return PackageContent(
            spec_path= helpers.locate_spec(self.workdir),
            source_paths=helpers.locate_sources(self.workdir))


class RubyGemsProvider(PackageContentProvider):
    def get_content(self, task):
        gem_name = task.source_data['gem_name'].strip()
        spec_path = os.path.join(self.workdir, '{}.spec'.format(gem_name))
        cmd = ['gem2rpm', gem_name, '-o', spec_path, '-C', self.workdir, '--fetch']
        result = helpers.run_cmd(cmd)

        source_paths = helpers.locate_sources(self.workdir)

        if "Empty tag: License" in result.stderr:
            raise PackageImportException("{}\n{}\n{}".format(
                error, "Not specifying a license means all rights are reserved; others have no rights to use the code for any purpose.",
                "See http://guides.rubygems.org/specification-reference/#license="))

        return PackageContent(spec_path=spec_path, source_paths=source_paths)


class SrpmUrlProvider(PackageContentProvider):
    def get_content(self, task):
        srpm_path = helpers.download_file(task.source_data['url'], self.workdir)

        try:
            helpers.extract_srpm(srpm_path, self.workdir)
        except subprocess.CalledProcessError as e:
            log.error("CalledProcessError: {}".format(e.output))
            raise PackageImportException(str(e))

        spec_path = helpers.locate_spec(self.workdir)
        source_paths = helpers.locate_sources(self.workdir)

        extra_content = []
        for path in glob.glob(os.path.join(self.workdir, '*')):
            if path != spec_path and path not in source_paths:
               extra_content.append(path)

        return PackageContent(
            spec_path=spec_path,
            source_paths=source_paths,
            extra_content=extra_content)


class SpecUrlProvider(PackageContentProvider):
    def get_content(self, task):
        spec_path = helpers.download_file(task.source_data['url'], self.workdir)
        return PackageContent(spec_path=spec_path)


class DistGitProvider(PackageContentProvider):
    def get_content(self, task):
        cmd = ['git', 'clone', task.source_data['clone_url'], self.workdir]
        result = helpers.run_cmd(cmd)
        log.info(result)

        jinja_env = Environment(loader=FileSystemLoader(
            os.path.join(os.path.dirname(__file__), 'templates')))
        template = jinja_env.get_template('fedpkg.conf.j2')

        parse = urlparse(task.source_data['clone_url'])
        distgit_domain = parse.netloc
        cfg = template.render(distgit_domain=distgit_domain, scheme=parse.scheme)
        log.info(cfg)

        config_path = os.path.join(self.workdir, 'fedpkg.conf')
        f = open(config_path, "w+")
        f.write(cfg)
        f.close()

        if task.source_data['branch']:
            self.checkout(task.source_data['branch'], self.workdir)

        # Run distgit client to obtain package sources
        cmd = ['fedpkg', '--config', 'fedpkg.conf',
               '--module-name', self.module_name(parse.path), 'sources']
        result = helpers.run_cmd(cmd, cwd=self.workdir)
        log.info(result)

        return PackageContent(
            spec_path= helpers.locate_spec(self.workdir),
            source_paths=helpers.locate_sources(self.workdir))

    def checkout(self, branch, cwd):
        cmd = ['git', 'checkout', branch]
        try:
            helpers.run_cmd(cmd, cwd=cwd)
        except OSError as e:
            raise PackageImportException(str(e))

    def module_name(self, url_path):
        return re.sub(".git$", "", re.sub("^/c?git/", "", url_path))
