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
from coprs.logic.packages_logic import PackagesLogic
from coprs.logic.complex_logic import ComplexLogic

SCM_SOURCE_TYPE = '8'

logging.basicConfig(
    filename="{0}/build_on_pagure_commit.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)

PAGURE_BASE_URL = "https://pagure.io/"

class SCMPackage(object):
    def __init__(self, db_row):
        source_json_dict = json.loads(db_row.source_json)
        self.pkg_id = db_row.package_id
        self.clone_url = source_json_dict.get('clone_url')
        self.committish = source_json_dict.get('committish', '')
        self.subdirectory = source_json_dict.get('subdirectory', '')
        self.spec = source_json_dict.get('spec', '')
        self.copr_id = db_row.copr_id
        self.copr = CoprsLogic.get_by_id(self.copr_id).first()
        self.package = ComplexLogic.get_package_by_id_safe(self.pkg_id)

    def build(self):
        PackagesLogic.build_package(self.copr.user, self.copr, self.package)
        db.session.commit()

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
            """.format(SCM_SOURCE_TYPE, true, placeholder=placeholder), '%'+clone_url_subpart+'%'
        )
        return [SCMPackage(row) for row in rows]

    def is_dir_in_commit(self, raw_commit_text):
        if not self.git_dir or not raw_commit_text:
            return True

        for line in raw_commit_text.split('\n'):
            match = re.search(r'^(\+\+\+|---) [ab]/(\w*)/.*$', line)
            if match and match.group(2).lower() == self.git_dir.lower():
                return True

        return False


class SCMPackage(Package):


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
        evts = poller.poll(10000)
        if not evts:
            continue

        log.debug("Receiving...")
        topic, msg = s.recv_multipart()

        log.debug("Parsing...")
        data = json.loads(msg)

        namespace = data['msg']['repo']['namespace']
        repo_name = data['msg']['repo']['name']
        branch = data['msg']['branch']
        start_commit = data['msg']['start_commit']
        end_commit = data['msg']['end_commit']

        if namespace:
            clone_url_subpart = '/' + namespace + '/' + repo_name
        else:
            clone_url_subpart = '/' + repo_name

        log.info("MSG:")
        log.info("\tclone_url_subpart = {}".format(clone_url_subpart))
        log.info("\tbranch = {}".format(branch))

        tito_candidates = Package.get_candidates_for_rebuild(TITO_TYPE, clone_url_subpart)
        scm_candidates = Package.get_candidates_for_rebuild(MOCK_SCM_TYPE, clone_url_subpart)

        raw_commit_text = None
        # if start_commit != end_commit, then more than one commit and no means to iterate over
        if tito_candidates and start_commit == end_commit:
            raw_commit_url = PAGURE_BASE_URL + clone_url_subpart + '/raw/' + start_commit
            r = requests.get(raw_commit_url)
            if r.status_code == requests.codes.ok:
                raw_commit_text = r.text
            else:
                log.error("Bad http status {0} from url {1}".format(r.status_code, raw_commit_url))

        for pkg in tito_candidates:
            log.info("Considering pkg id:{}, source_json:{}".format(pkg.pkg_id, pkg.source_json))
            if (pkg.git_url.endswith(clone_url_subpart) or pkg.git_url.endswith(clone_url_subpart+'.git')) \
                    and (not pkg.git_branch or branch.endswith('/'+pkg.git_branch)) \
                    and pkg.is_dir_in_commit(raw_commit_text):
                log.info("\t -> rebuilding.")
                pkg.build()
            else:
                log.info("\t -> skipping.")

        for pkg in scm_candidates:
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
