#!/usr/bin/python3

import argparse
import sys
import os
import json
import re
import logging

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

# pylint: disable=wrong-import-position

from copr_common.request import SafeRequest

from coprs import db, app, helpers
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.packages_logic import PackagesLogic
from coprs.exceptions import BadRequest

logging.basicConfig(
    filename="{0}/check_for_anitya_version_updates.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.INFO)
log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))


def _get_parser():
    parser = argparse.ArgumentParser(description='Fetch package version updates by using datagrepper log of anitya emitted messages and issue rebuilds of the respective COPR packages for each such update. Requires httpie package.')

    parser.add_argument('--backend', action='store', default='pypi', choices=['pypi', 'rubygems'],
                       help='only check for updates from backend BACKEND, default pypi')
    parser.add_argument('--delta', action='store', type=int, metavar='SECONDS', default=86400,
                       help='ignore updates older than SECONDS, default 86400')
    parser.add_argument('-v', '--version', action='version', version='1.0',
                       help='print program version and exit')
    return parser


def _get_json(url):
    requestor = SafeRequest(log=log)
    return requestor.get(url).json()


def get_updates_messages(delta):
    url_template = 'https://apps.fedoraproject.org/datagrepper/raw?category=anitya&delta={delta}&topic=org.release-monitoring.prod.anitya.project.version.update&rows_per_page=64&order=asc&page={page}'
    url = url_template.format(delta=delta, page=1)
    result_json = _get_json(url)
    messages = result_json['raw_messages']
    pages = result_json['pages']

    for p in range(2, pages+1):
        url = url_template.format(delta=delta, page=p)
        result_json = _get_json(url)
        messages += result_json['raw_messages']

    return messages

def get_updated_packages(updates_messages, backend):
    updated_packages = {}
    for message in updates_messages:
        update = message['msg']
        project = update['project']
        projectname = project['name'].lower()
        if backend != project['backend'].lower():
            continue
        version = project['version']
        if not is_stable_release(version):
            continue
        log.debug("Updated %s package %s = %s", backend, projectname, version)
        updated_packages[projectname] = version
    return updated_packages


class RebuilderInterface:
    """
    Helper for re-building a package according to the build "backend" method.
    """
    def build(self, copr, package, new_updated_version):
        """
        Create a new package build in database.
        """
        raise NotImplementedError

    def source_json_version(self, dict_data):
        """
        Reading the dict with parsed source_json() try to detect the version of
        the package.  This is a best-effort attempt (can return None)
        """
        raise NotImplementedError



class GemsRebuilder(RebuilderInterface):
    """
    Rebuilder for RubyGems (source_type=6)
    """
    def __init__(self, source_json):
        self.name = source_json['gem_name'].lower()

    def build(self, copr, package, new_updated_version):
        return BuildsLogic.create_new_from_rubygems(
            copr.user,
            copr,
            self.name,
            chroot_names=None,
            package=package,
        )

    def source_json_version(self, dict_data):
        """
        Source JSON for rubygems method doesn't support Gems versions.
        """
        return None


class PyPiRebuilder(RebuilderInterface):
    """
    Rebuilder for PyPI (source_type=5)
    """
    def __init__(self, source_json):
        self.name = source_json['pypi_package_name'].lower()
        self.python_versions = source_json['python_versions']
        self.spec_template = source_json.get('spec_template')
        self.spec_generator = source_json.get("spec_generator")

    def build(self, copr, package, new_updated_version):
        return BuildsLogic.create_new_from_pypi(
            copr.user,
            copr,
            self.name,
            new_updated_version,
            self.spec_generator,
            self.spec_template,
            self.python_versions,
            chroot_names=None,
            background=True,
            package=package,
        )

    def source_json_version(self, dict_data):
        return dict_data.get("pypi_package_version", None)

def package_from_source(backend, source_json):
    try:
        return {
            'pypi': PyPiRebuilder,
            'rubygems': GemsRebuilder,
        }[backend](source_json)
    except KeyError:
        raise Exception('Unsupported backend {0} passed as command-line argument'.format(backend))


def is_stable_release(version: str) -> bool:
    """
    Return True if the given VERSION string appears to be a stable release,
    and return False for pre- and post- releases.
    """
    # Helper to diagnose leftovers:
    # $ grep Updated /var/log/copr-frontend/check_for_anitya_version_updates.log \
    #         | grep pypi | sed '/= \([0-9]\+\(\.\)\?\)\+$/d'
    known_prerelease_patterns = [
        "dev",
        "beta",
        "rc",
        "alpha",
        "post",  # mct-nightly 1.7.1.31122022.post351
        "a",  # openapi-core (python-openapi-core) version 0.17.0a1 in @copr/PyPI
        "b",  # fiona (python-fiona) version 1.9b2 in @copr/PyPI
    ]
    for pattern in known_prerelease_patterns:
        if pattern in version:
            return False
    return True

def main():
    args = _get_parser().parse_args()
    backend = args.backend.lower()
    updated_packages = get_updated_packages(get_updates_messages(args.delta), backend)
    log.info("Updated packages per datagrepper %s", len(updated_packages))
    for package, last_build in PackagesLogic.webhook_package_candidates(
            helpers.BuildSourceEnum(args.backend.lower())):
        source_json = json.loads(package.source_json)
        rebuilder = package_from_source(backend, source_json)
        log.debug(
            "candidate %s package %s in %s",
            args.backend,
            rebuilder.name,
            package.copr.full_name,
        )

        if rebuilder.name not in updated_packages:
            continue

        new_updated_version = updated_packages[rebuilder.name]
        last_version = None
        if last_build:
            last_version = last_build.pkg_version
            if not last_version:
                source_data = json.loads(last_build.source_json)
                last_version = rebuilder.source_json_version(source_data)

            if not last_version and not last_build.finished:
                log.debug("Skipping %s %s in %s, existing build %s",
                          package.name, new_updated_version,
                          package.copr.full_name, last_build.id)
                continue

        log.debug(
            "checking %s (pkg_name %s), last version: %s, new version %s",
            rebuilder.name,
            package.name,
            last_version,
            new_updated_version,
        )

        if last_version and re.match(new_updated_version, last_version):
            # already built
            continue

        # rebuild if the last build's package version is "different" from new
        # remote package version
        try:
            rebuilder.build(package.copr, package, new_updated_version)
            log.info(
                "Launched build for %s (%s) version %s in %s",
                rebuilder.name, package.name, new_updated_version,
                package.copr.full_name,
            )
        except BadRequest as exc:
            log.error("Can't submit a build: %s", str(exc))

    db.session.commit()

if __name__ == '__main__':
    try:
        with app.app_context():
            main()
    except Exception as e:
        log.exception(str(e))
