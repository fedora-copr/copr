#!/usr/bin/env python3

import json
import zmq
import sys
import os
import logging

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

from coprs import db, app, models
from coprs.logic.coprs_logic import CoprsLogic
from coprs.logic.builds_logic import BuildsLogic

logging.basicConfig(
    filename='{0}/src-fp-stg-ci.log'.format(app.config.get('LOG_DIR')),
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.DEBUG)
log = logging.getLogger(__name__)
log.addHandler(logging.StreamHandler(sys.stdout))

ENDPOINT = 'tcp://hub.fedoraproject.org:9940'
TOPIC = 'io.pagure.prod.pagure.pull-request.new'
CLONE_URL_TEMPLATE = 'https://pagure.io/{path}.git'
CHROOTS = ['fedora-rawhide-x86_64', 'fedora-rawhide-ppc64le',
           'fedora-27-x86_64', 'fedora-27-ppc64le',
           'fedora-26-x86_64', 'fedora-26-ppc64le',
           'fedora-26-x86_64', 'fedora-26-ppc64le',
           'epel-7-x86_64', 'epel-7-ppc64le']

def ci_listener():
    log.debug('Setting up poller...')
    ctx = zmq.Context()
    s = ctx.socket(zmq.SUB)
    s.connect(ENDPOINT)

    s.setsockopt(zmq.SUBSCRIBE, TOPIC)

    poller = zmq.Poller()
    poller.register(s, zmq.POLLIN)

    while True:
        log.debug('Polling...')
        evts = poller.poll(10000)
        if not evts:
            continue

        log.debug('Receiving...')
        topic, msg = s.recv_multipart()

        log.debug('Parsing...')
        msg = json.loads(msg)

        log.debug('Handling pagure msg %r' % msg.get('msg_id', None))
        prid = msg['msg']['pullrequest']['id']
        package = msg['msg']['pullrequest']['repo_from']['name']
        namespace = msg['msg']['pullrequest']['repo_from']['namespace']
        url_path = msg['msg']['pullrequest']['repo_from']['fullname']
        commit = msg['msg']['pullrequest']['commit_stop']
        username = msg['msg']['pullrequest']['repo_from']['user']['name']
        clone_url = CLONE_URL_TEMPLATE.format(path=url_path)

        log.info('RECEIVED DATA:')
        log.info('prid = {}'.format(prid))
        log.info('username = {}'.format(username))
        log.info('package = {}'.format(package))
        log.info('namespace = {}'.format(namespace))
        log.info('url_path = {}'.format(url_path))
        log.info('commit = {}'.format(commit))
        log.info('clone_url = {}'.format(clone_url))

        if namespace:
            coprname = '{namespace}-{package}-PR{prid}'.format(**{
                'namespace': namespace,
                'package': package,
                'prid': prid
            })
        else:
            coprname = '{package}-PR{prid}'.format(**{
                'package': package,
                'prid': prid
            })

        user = models.User.query.filter(models.User.username == username).first()

        if not user:
            user = models.User(
                username=username, mail="")
            db.session.add(user)

        copr = (models.Copr.query
               .filter(models.Copr.name == coprname)
               .filter(models.Copr.user_id == user.id)).first()

        if not copr:
            copr = CoprsLogic.add(
                name=coprname,
                user=user,
                selected_chroots=CHROOTS,
                check_for_duplicates=True)
            db.session.add(copr)

        build = BuildsLogic.create_new_from_scm(user, copr, 'git', clone_url, commit)

        log.info('Starting build for PR {prid} in {user}/{project}'.format(
            prid=prid, user=username, project=coprname))
        db.session.commit()


if __name__ == '__main__':
    while True:
        try:
            ci_listener()
        except KeyboardInterrupt:
            sys.exit(1)
        except:
            log.exception('Error in fedmsg loop. Restarting it.')
