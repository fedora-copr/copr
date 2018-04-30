#!/usr/bin/env python3

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
from coprs.logic.complex_logic import ComplexLogic
from coprs import helpers

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

SCM_SOURCE_TYPE = helpers.BuildSourceEnum("scm")

logging.basicConfig(
    filename="{0}/build_on_pagure_commit.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)

log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))

PAGURE_BASE_URL = "https://pagure.io/"
SRCFPO_BASE_URL = "https://src.fedoraproject.org/"

ENDPOINT = 'tcp://hub.fedoraproject.org:9940'

TOPICS = ['io.pagure.prod.pagure.git.receive', 'org.fedoraproject.prod.pagure.git.receive']

class ScmPackage(object):
    def __init__(self, db_row):
        self.pkg_id = db_row.package_id
        self.copr_id = db_row.copr_id

        self.source_json_dict = json.loads(db_row.source_json)
        self.clone_url = self.source_json_dict.get('clone_url') or ''
        self.committish = self.source_json_dict.get('committish') or ''
        self.subdirectory = self.source_json_dict.get('subdirectory') or ''

        self.package = ComplexLogic.get_package_by_id_safe(self.pkg_id)

    def build(self, branch):
        BuildsLogic.rebuild_package(self.package, {'committish': branch})
        db.session.commit()

    @classmethod
    def get_candidates_for_rebuild(cls, clone_url):
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
            WHERE package.source_type = {0} AND
                  package.webhook_rebuild = {1} AND
                  package.source_json ILIKE {placeholder}
            """.format(SCM_SOURCE_TYPE, true, placeholder=placeholder), '%'+clone_url+'%'
        )
        return [ScmPackage(row) for row in rows]

    def is_dir_in_commit(self, raw_commit_text):
        if not self.subdirectory or not raw_commit_text:
            return True

        for line in raw_commit_text.split('\n'):
            match = re.search(r'^(\+\+\+|---) [ab]/(\w*)/?.*$', line)
            if match and match.group(2).lower() == self.subdirectory.strip('./').lower():
                return True

        return False


def build_on_fedmsg_loop():
    log.debug("Setting up poller...")

    ctx = zmq.Context()
    s = ctx.socket(zmq.SUB)
    s.connect(ENDPOINT)

    for topic in TOPICS:
        s.setsockopt_string(zmq.SUBSCRIBE, topic)

    poller = zmq.Poller()
    poller.register(s, zmq.POLLIN)

    while True:
        log.debug("Polling...")
        evts = poller.poll(10000)
        if not evts:
            continue

        log.debug("Receiving...")
        _, msg_bytes = s.recv_multipart()
        msg = msg_bytes.decode("utf-8")

        log.debug("Parsing...")
        data = json.loads(msg)

        log.info("Got topic: {}".format(data['topic']))

        project_url_path = data['msg']['repo']['url_path']
        clone_url_path = data['msg']['repo']['fullname']
        branch = data['msg']['branch']
        start_commit = data['msg']['start_commit']
        end_commit = data['msg']['end_commit']

        if data['topic'] == 'org.fedoraproject.prod.pagure.git.receive':
            base_url = SRCFPO_BASE_URL
        else:
            base_url = PAGURE_BASE_URL

        clone_url = base_url + clone_url_path
        log.info("\tclone_url = {}".format(clone_url))
        log.info("\tbranch = {}".format(branch))

        candidates = ScmPackage.get_candidates_for_rebuild(clone_url)
        raw_commit_text = None
        if candidates:
            # if start_commit != end_commit
            # then more than one commit and no means to iterate over :(
            raw_commit_url = base_url + project_url_path + '/raw/' + end_commit
            r = requests.get(raw_commit_url)
            if r.status_code == requests.codes.ok:
                raw_commit_text = r.text
            else:
                log.error("Bad http status {0} from url {1}".format(r.status_code, raw_commit_url))

        for pkg in candidates:
            log.info("Considering pkg id: {}, source_json: {}".format(pkg.pkg_id, pkg.source_json_dict))
            if (pkg.clone_url == clone_url or pkg.clone_url == clone_url+'.git') \
                    and (not pkg.committish or branch.endswith(pkg.committish)) \
                    and pkg.is_dir_in_commit(raw_commit_text):
                log.info("\t -> rebuilding.")
                pkg.build(end_commit)
            else:
                log.info("\t -> skipping.")


if __name__ == '__main__':
    while True:
        try:
            build_on_fedmsg_loop()
        except KeyboardInterrupt:
            sys.exit(1)
        except:
            log.exception('Error in fedmsg loop. Restarting it.')
