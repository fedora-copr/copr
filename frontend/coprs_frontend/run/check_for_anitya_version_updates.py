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

from coprs import db, app, helpers
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.coprs_logic import CoprsLogic

logging.basicConfig(
    filename="{0}/check_for_anitya_version_updates.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))

parser = argparse.ArgumentParser(description='Fetch package version updates by using datagrepper log of anitya emitted messages and issue rebuilds of the respective COPR packages for each such update. Requires httpie package.')

parser.add_argument('--backend', action='store', default='pypi', choices=['pypi', 'rubygems'],
                   help='only check for updates from backend BACKEND, default pypi')
parser.add_argument('--delta', action='store', type=int, metavar='SECONDS', default=86400,
                   help='ignore updates older than SECONDS, default 86400')
parser.add_argument('-v', '--version', action='version', version='1.0',
                   help='print program version and exit')

args = parser.parse_args()


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

def get_updates_messages():
    cmd_binary = 'curl'
    url_template = 'https://apps.fedoraproject.org/datagrepper/raw?category=anitya&delta={delta}&topic=org.release-monitoring.prod.anitya.project.version.update&rows_per_page=64&order=asc&page={page}'
    get_updates_cmd = [cmd_binary, url_template.format(delta=args.delta, page=1)]
    result_json = to_json(run_cmd(get_updates_cmd))
    messages = result_json['raw_messages']
    pages = result_json['pages']

    for p in range(2, pages+1):
        get_updates_cmd = [cmd_binary, url_template.format(delta=args.delta, page=p)]
        result_json = to_json(run_cmd(get_updates_cmd))
        messages += result_json['raw_messages']

    return messages

def get_updated_packages(updates_messages):
    updated_packages = {}
    for message in updates_messages:
        update = message['msg']
        project = update['project']
        if args.backend.lower() != project['backend'].lower():
            continue
        updated_packages[project['name'].lower()] = project['version']
    return updated_packages

def get_copr_package_info_rows(updated_packages):
    pkg_name_pattern = '(' + '|'.join(updated_packages.keys()) + ')'
    source_type = helpers.BuildSourceEnum(args.backend.lower())
    if db.engine.url.drivername == "sqlite":
        placeholder = '?'
        true = '1'
    else:
        placeholder = '%s'
        true = 'true'
    rows = db.engine.execute(
        """
        SELECT package.id AS package_id, package.source_json AS source_json, build.pkg_version AS pkg_version, package.copr_id AS copr_id
        FROM package
        LEFT OUTER JOIN build ON build.package_id = package.id
        WHERE package.source_type = {placeholder} AND
              package.source_json ~* '{pkg_name_pattern}' AND
              package.webhook_rebuild = {true} AND
              (build.id is NULL OR build.id = (SELECT MAX(build.id) FROM build WHERE build.package_id = package.id));
        """.format(placeholder=placeholder, pkg_name_pattern=pkg_name_pattern, true=true), source_type
    )
    return rows


class RubyGemsPackage(object):
    def __init__(self, source_json):
        self.name = source_json['gem_name'].lower()

    def build(self, copr, new_update_version):
        return BuildsLogic.create_new_from_rubygems(copr.user, copr, self.name, chroot_names=None)


class PyPIPackage(object):
    def __init__(self, source_json):
        self.name = source_json['pypi_package_name'].lower()
        self.python_versions = source_json['python_versions']
        self.spec_template = source_json['spec_template']

    def build(self, copr, new_updated_version):
        return BuildsLogic.create_new_from_pypi(
            copr.user,
            copr,
            self.name,
            new_updated_version,
            "pyp2rpm",
            self.spec_template,
            self.python_versions,
            chroot_names=None
        )


def package_from_source(backend, source_json):
    try:
        return {
            'pypi': PyPIPackage,
            'rubygems': RubyGemsPackage,
        }[backend](source_json)
    except KeyError:
        raise Exception('Unsupported backend {0} passed as command-line argument'.format(args.backend))


def main():
    updated_packages = get_updated_packages(get_updates_messages())
    log.info('Updated packages according to datagrepper: {0}'.format(updated_packages))

    for row in get_copr_package_info_rows(updated_packages):
        source_json = json.loads(row.source_json)
        package = package_from_source(args.backend.lower(), source_json)

        latest_build_version = row.pkg_version
        log.info('candidate package for rebuild: {0}, package_id: {1}, copr_id: {2}'.format(package.name, row.package_id, row.copr_id))
        if package.name in updated_packages:
            new_updated_version = updated_packages[package.name]
            log.debug('name: {0}, latest_build_version: {1}, new_updated_version {2}'.format(package.name, latest_build_version, new_updated_version))

            # if the last build's package version is "different" from new remote package version, rebuild
            if not latest_build_version or not re.match(new_updated_version, latest_build_version):
                try:
                    copr = CoprsLogic.get_by_id(row.copr_id)[0]
                except Exception as e:
                    log.exception(e)
                    continue

                log.info('Launching {} build for package of source name: {}, package_id: {}, copr_id: {}, user_id: {}'
                        .format(args.backend.lower(), package.name, row.package_id, copr.id, copr.user.id))
                build = package.build(copr, new_updated_version)
                db.session.commit()
                log.info('Launched build id {0}'.format(build.id))

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        log.exception(str(e))
