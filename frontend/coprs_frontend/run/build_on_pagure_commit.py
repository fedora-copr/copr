#!/usr/bin/env python

import json
import pprint
import zmq
import sys
import os
import logging
import requests
import re

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

from coprs import db, app
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic

TITO_TYPE = '3'
MOCK_SCM_TYPE = '4'

logging.basicConfig(
    filename="{0}/build_on_pagure_commit.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)

PAGURE_BASE_URL = "https://pagure.io/"


class Package(object):
    def build(self):
        raise NotImplemented()

    @classmethod
    def new_from_db_row(cls, source_type, row):
        try:
            return {
                TITO_TYPE: GitAndTitoPackage,
                MOCK_SCM_TYPE: MockSCMPackage,
            }[source_type](row)
        except KeyError:
            raise Exception('Unsupported package type {}'.format(source_type))

    @classmethod
    def get_candidates_for_rebuild(cls, source_type, clone_url_subpart):
        if db.engine.url.drivername == "sqlite":
            placeholder = '?'
            true = '1'
        else:
            placeholder = '%s'
            true = 'true'

        rows = db.engine.execute(
            """
            SELECT package.id AS package_id, package.source_json AS source_json, package.copr_id AS copr_id
            FROM package
            WHERE package.source_type = '{0}' AND
                  package.webhook_rebuild = {1} AND
                  package.source_json ILIKE {placeholder}
            """.format(source_type, true, placeholder=placeholder), '%'+clone_url_subpart+'%'
        )
        return [Package.new_from_db_row(source_type, row) for row in rows]


class GitAndTitoPackage(Package):
    def __init__(self, db_row):
        source_json = json.loads(db_row.source_json)
        self.pkg_id = db_row.package_id
        self.git_url = source_json['git_url']
        self.git_branch = source_json['git_branch']
        self.git_dir = source_json['git_dir']
        self.tito_test = source_json['tito_test']
        self.copr_id = db_row.copr_id
        self.copr = CoprsLogic.get_by_id(self.copr_id).first()
        self.source_json = db_row.source_json

    def build(self):
        BuildsLogic.create_new_from_tito(self.copr.user, self.copr, self.git_url, self.git_dir, self.git_branch, self.tito_test)
        db.session.commit()

    def is_dir_in_commit(self, data, clone_url_subpart):
        if not self.git_dir:
            return True # simplest case

        start_commit = data['msg']['start_commit']
        end_commit = data['msg']['end_commit']

        if start_commit != end_commit:
            return True # more than one commit and no means to iterate over

        raw_commit_url = PAGURE_BASE_URL + clone_url_subpart + '/raw/' + start_commit
        r = requests.get(raw_commit_url)
        if r.status_code != requests.codes.ok:
            log.error("Bad http status {0} from url {1}".format(r.status_code, raw_commit_url))
            return False

        for line in r.text.split('\n'):
            match = re.search(r'^(\+\+\+|---) [ab]/(\w*)/.*$', line)
            if match and match.group(2).lower() == self.git_dir.lower():
                return True

        return False


class MockSCMPackage(Package):
    def __init__(self, db_row):
        source_json = json.loads(db_row.source_json)
        self.pkg_id = db_row.package_id
        self.scm_url = source_json['scm_url']
        self.scm_branch = source_json['scm_branch']
        self.scm_type = source_json['scm_type']
        self.spec = source_json['spec']
        self.copr_id = db_row.copr_id
        self.copr = CoprsLogic.get_by_id(self.copr_id).first()
        self.source_json = db_row.source_json

    def build(self):
        BuildsLogic.create_new_from_mock(self.copr.user, self.copr, self.scm_type, self.scm_url, self.scm_branch, self.spec)
        db.session.commit()


def build_on_fedmsg_loop():
    log.debug("Setting up poller...")

    endpoint = 'tcp://hub.fedoraproject.org:9940'
    topic = 'io.pagure.prod.pagure.git.receive'

    ctx = zmq.Context()
    s = ctx.socket(zmq.SUB)
    s.connect(endpoint)

    s.setsockopt(zmq.SUBSCRIBE, topic)

    poller = zmq.Poller()
    poller.register(s, zmq.POLLIN)

    while True:
        log.debug("Polling...")
        evts = poller.poll()  # This blocks until a message arrives

        log.debug("Receiving...")
        topic, msg = s.recv_multipart()

        log.debug("Parsing...")
        data = json.loads(msg)

        namespace = data['msg']['repo']['namespace']
        repo_name = data['msg']['repo']['name']
        branch = data['msg']['branch']

	if namespace:
	    clone_url_subpart = '/' + namespace + '/' + repo_name
	else:
	    clone_url_subpart = '/' + repo_name

	log.info("MSG:")
	log.info("\tclone_url_subpart = {}".format(clone_url_subpart))
	log.info("\tbranch = {}".format(branch))

        for pkg in Package.get_candidates_for_rebuild(TITO_TYPE, clone_url_subpart):
            log.info("Considering pkg id:{}, source_json:{}".format(pkg.pkg_id, pkg.source_json))
            if (pkg.git_url.endswith(clone_url_subpart) or pkg.git_url.endswith(clone_url_subpart+'.git')) \
                    and (not pkg.git_branch or branch.endswith('/'+pkg.git_branch)) and pkg.is_dir_in_commit(data, clone_url_subpart):
                log.info("\t -> rebuilding.")
                pkg.build()
            else:
                log.info("\t -> skipping.")

        for pkg in Package.get_candidates_for_rebuild(MOCK_SCM_TYPE, clone_url_subpart):
            log.info("Considering pkg id:{}, source_json:{}".format(pkg.pkg_id, pkg.source_json))
            if (pkg.scm_url.endswith(clone_url_subpart) or pkg.scm_url.endswith(clone_url_subpart+'.git')) \
                    and (not pkg.scm_branch or branch.endswith('/'+pkg.scm_branch)):
                log.info("\t -> rebuilding.")
                pkg.build()
            else:
                log.info("\t -> skipping.")

if __name__ == '__main__':
    while True:
        try:
            build_on_fedmsg_loop()
        except:
            log.exception("Error in fedmsg loop. Restarting it.")
