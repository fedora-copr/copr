#!/usr/bin/python3

import subprocess
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

from coprs import db, app, helpers
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.packages_logic import PackagesLogic

logging.basicConfig(
    filename="{0}/check_for_anitya_version_updates.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
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


def run_cmd(cmd):
    """
    Run given command in a subprocess
    """
    log.info('Executing: '+' '.join(cmd))
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (stdout, stderr) = process.communicate()
    if process.returncode != 0:
        log.error(stderr)
        sys.exit(1)
    return stdout

def to_json(data_bytes):
    try:
        data = data_bytes.decode("utf-8")
        data_json = json.loads(data)
    except Exception as e:
        log.info(data)
        log.exception(str(e))
    return data_json

def get_updates_messages(delta):
    cmd_binary = 'curl'
    url_template = 'https://apps.fedoraproject.org/datagrepper/raw?category=anitya&delta={delta}&topic=org.release-monitoring.prod.anitya.project.version.update&rows_per_page=64&order=asc&page={page}'
    get_updates_cmd = [cmd_binary, url_template.format(delta=delta, page=1)]
    result_json = to_json(run_cmd(get_updates_cmd))
    messages = result_json['raw_messages']
    pages = result_json['pages']

    for p in range(2, pages+1):
        get_updates_cmd = [cmd_binary, url_template.format(delta=delta, page=p)]
        result_json = to_json(run_cmd(get_updates_cmd))
        messages += result_json['raw_messages']

    return messages

def get_updated_packages(updates_messages, backend):
    updated_packages = {}
    for message in updates_messages:
        update = message['msg']
        project = update['project']
        if backend != project['backend'].lower():
            continue
        updated_packages[project['name'].lower()] = project['version']
    return updated_packages

class RubyGemsPackage(object):
    def __init__(self, source_json):
        self.name = source_json['gem_name'].lower()

    def build(self, copr, new_update_version):
        return BuildsLogic.create_new_from_rubygems(copr.user, copr, self.name, chroot_names=None)


class PyPIPackage(object):
    def __init__(self, source_json):
        self.name = source_json['pypi_package_name'].lower()
        self.python_versions = source_json['python_versions']
        self.spec_template = source_json.get('spec_template')
        self.spec_generator = source_json.get("spec_generator")

    def build(self, copr, new_updated_version):
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
        )

def package_from_source(backend, source_json):
    try:
        return {
            'pypi': PyPIPackage,
            'rubygems': RubyGemsPackage,
        }[backend](source_json)
    except KeyError:
        raise Exception('Unsupported backend {0} passed as command-line argument'.format(backend))


def is_prerelease(version: str) -> bool:
    """
    Detect a pre-release version string.
    """
    known_prerelease_patterns = [
        "dev",
        "beta",
        "rc",
        "alpha",
        "b",  # fiona (python-fiona) version 1.9b2 in @copr/PyPI
    ]
    for pattern in known_prerelease_patterns:
        if pattern in version:
            return True
    return False

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

        last_version = last_build.pkg_version if last_build else None

        new_updated_version = updated_packages[rebuilder.name]
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

        if is_prerelease(new_updated_version):
            continue

        # rebuild if the last build's package version is "different" from new
        # remote package version
        rebuilder.build(package.copr, new_updated_version)
        log.info(
            "Launched build for %s (%s) version %s in %s",
            rebuilder.name, package.name, new_updated_version,
            package.copr.full_name,
        )

    db.session.commit()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log.exception(str(e))
