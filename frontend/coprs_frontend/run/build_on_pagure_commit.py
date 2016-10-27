#!/usr/bin/env python

import json
import pprint
import zmq
import sys
import os
import logging

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

from coprs import db, app
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic

MOCK_SCM_TYPE = '4'
TITO_TYPE = '3'

logging.basicConfig(
    filename="{0}/build_on_pagure_commit.log".format(app.config.get("LOG_DIR")),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)

def logdebug(msg):
    print msg
    log.debug(msg)

def loginfo(msg):
    print msg
    log.info(msg)

def logerror(msg):
    print >> sys.stderr, msg
    log.error(msg)

def logexception(msg):
    print >> sys.stderr, msg
    log.exception(msg)

def get_candidates_for_rebuild(source_type, clone_url_subpart):
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
    return rows


class GitAndTitoPackage(object):
    def __init__(self, source_json):
        self.git_url = source_json['git_url']
        self.git_branch = source_json['git_branch']
        self.git_dir = source_json['git_dir']
        self.tito_test = source_json['tito_test']

    def build(self, copr):
        return BuildsLogic.create_new_from_tito(copr.user, copr, self.git_url, self.git_dir, self.git_branch, self.tito_test)


class MockSCMPackage(object):
    def __init__(self, source_json):
        self.scm_url = source_json['scm_url']
        self.scm_branch = source_json['scm_branch']
        self.scm_type = source_json['scm_type']
        self.spec = source_json['spec']

    def build(self, copr):
        return BuildsLogic.create_new_from_mock(copr.user, copr, self.scm_type, self.scm_url, self.scm_branch, self.spec)


def package_from_source(source_type, source_json):
    try:
        return {
            TITO_TYPE: GitAndTitoPackage,
            MOCK_SCM_TYPE: MockSCMPackage,
        }[source_type](source_json)
    except KeyError:
        raise Exception('Unsupported backend {0} passed as command-line argument'.format(args.backend))


def exec_builds_on_fedmsg_loop():
    endpoint = 'tcp://hub.fedoraproject.org:9940'
    topic = 'io.pagure.prod.pagure.git.receive'

    ctx = zmq.Context()
    s = ctx.socket(zmq.SUB)
    s.connect(endpoint)

    s.setsockopt(zmq.SUBSCRIBE, topic)

    poller = zmq.Poller()
    poller.register(s, zmq.POLLIN)

    while True:
        evts = poller.poll()  # This blocks until a message arrives
        topic, msg = s.recv_multipart()
        data = json.loads(msg)
        namespace = data['msg']['repo']['namespace']
        repo_name = data['msg']['repo']['name']
        branch = data['msg']['branch']

	if namespace:
	    clone_url_subpart = '/' + namespace + '/' + repo_name
	else:
	    clone_url_subpart = '/' + repo_name

	loginfo("MSG:")
	loginfo("\tclone_url_subpart = {}".format(clone_url_subpart))
	loginfo("\tbranch = {}".format(branch))

        for candidate in get_candidates_for_rebuild(TITO_TYPE, clone_url_subpart):
            project = CoprsLogic.get_by_id(candidate.copr_id)[0]
            pkg = package_from_source(TITO_TYPE, json.loads(candidate.source_json))
            loginfo("Considering candidate id:{}, source_json:{}".format(candidate.package_id, candidate.source_json))
            if (pkg.git_url.endswith(clone_url_subpart) or pkg.git_url.endswith(clone_url_subpart+'.git')) \
                    and (not pkg.git_branch or branch.endswith('/'+pkg.git_branch)):
                loginfo("\t -> rebuilding.")
                pkg.build(project)
                db.session.commit()
            else:
                loginfo("\t -> skipping.")

        for candidate in get_candidates_for_rebuild(MOCK_SCM_TYPE, clone_url_subpart):
            loginfo("Considering candidate id:{}, source_json:{}".format(candidate.package_id, candidate.source_json))
            project = CoprsLogic.get_by_id(candidate.copr_id).first()
            pkg = package_from_source(MOCK_SCM_TYPE, json.loads(candidate.source_json))
            if (pkg.scm_url.endswith(clone_url_subpart) or pkg.scm_url.endswith(clone_url_subpart+'.git')) \
                    and (not pkg.scm_branch or branch.endswith('/'+pkg.scm_branch)):
                loginfo("\t -> rebuilding.")
                pkg.build(project)
                db.session.commit()
            else:
                loginfo("\t -> skipping.")

if __name__ == '__main__':
    exec_builds_on_fedmsg_loop()
