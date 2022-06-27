#!/usr/bin/python3

import json
import pprint
import sys
import os
import requests
import re
import munch
import subprocess

sys.path.append(
    os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
)

from coprs import db, app, models
from coprs.logic.coprs_logic import CoprDirsLogic
from coprs.logic.builds_logic import BuildsLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs import helpers

from urllib.parse import urlparse

SUPPORTED_SOURCE_TYPES = [
    helpers.BuildSourceEnum("scm"),
    helpers.BuildSourceEnum("distgit"),
]

log = app.logger

TOPICS = {}
for topic, url in app.config["PAGURE_EVENTS"].items():
    TOPICS['{0}'.format(topic)] = url

def get_repeatedly(url):
    log.info("getting url {}".format(url))
    for attempt in range(1, 4):
        r = requests.get(url)
        if r.status_code == requests.codes.ok:
            return r.text
        else:
            log.error('Bad http status {0} from url {1}, attempt {2}'.format(
                r.status_code, url, attempt))
    # pagure down?
    return ""

class ScmPackage(object):
    def __init__(self, db_row):
        self.source_json_dict = json.loads(db_row.source_json)
        self.clone_url = self.source_json_dict.get('clone_url') or ''
        self.committish = self.source_json_dict.get('committish') or ''
        self.subdirectory = self.source_json_dict.get('subdirectory') or ''

        self.package = ComplexLogic.get_package_by_id_safe(db_row.id)
        self.copr = self.package.copr

    def build(self, source_dict_update, copr_dir, update_callback,
              scm_object_type, scm_object_id, scm_object_url, agent_url):

        if db.engine.url.drivername != 'sqlite':
            db.session.execute('LOCK TABLE build IN EXCLUSIVE MODE')

        return BuildsLogic.rebuild_package(
            self.package, source_dict_update, copr_dir, update_callback,
            scm_object_type, scm_object_id, scm_object_url, submitted_by=agent_url)

    @classmethod
    def get_candidates_for_rebuild(cls, clone_url):
        rows = models.Package.query \
            .join(models.Copr) \
            .filter(models.Copr.deleted.is_(False)) \
            .filter(models.Package.source_type.in_(SUPPORTED_SOURCE_TYPES)) \
            .filter(models.Package.webhook_rebuild) \
            .filter(models.Package.source_json.ilike('%' + clone_url + '%'))

        return [ScmPackage(row) for row in rows]


    def is_dir_in_commit(self, changed_files):
        if not changed_files:
            return False

        sm = helpers.SubdirMatch(self.subdirectory)
        for filename in changed_files:
            if sm.match(filename):
                return True

        return False


def event_info_from_pr_comment(data, base_url):
    """
    Message handler for updated pull-request opened in pagure.
    Topic: ``*.pagure.pull-request.comment.added``
    """
    if data['msg']['pullrequest']['status'] != 'Open':
        log.info('Pull-request not open, discarding.')
        return False

    if not data['msg']['pullrequest']['comments']:
        log.info('This is most odd, we\'re not seeing comments.')
        return False

    last_comment = data['msg']['pullrequest']['comments'][-1]
    if not last_comment:
        log.info('Can not access last comment, discarding.')
        return False

    if not 'comment' in last_comment or '[copr-build]' not in last_comment['comment']:
        log.info('The [copr-build] is not present in the message.')
        return False

    return munch.Munch({
        'object_id': data['msg']['pullrequest']['id'],
        'object_type': 'pull-request',
        'base_project_url_path': data['msg']['pullrequest']['project']['url_path'],
        'base_clone_url_path': data['msg']['pullrequest']['project']['fullname'],
        'base_clone_url': base_url + data['msg']['pullrequest']['project']['fullname'],
        'project_url_path': data['msg']['pullrequest']['repo_from']['url_path'],
        'clone_url_path': data['msg']['pullrequest']['repo_from']['fullname'],
        'clone_url': base_url + data['msg']['pullrequest']['repo_from']['fullname'],
        'branch_from': data['msg']['pullrequest']['branch_from'],
        'branch_to': data['msg']['pullrequest']['branch'],
        'start_commit': data['msg']['pullrequest']['commit_start'],
        'end_commit': data['msg']['pullrequest']['commit_stop'],
        'user': data['msg']['pullrequest']['user']['name'],
    })


def event_info_from_pr(data, base_url):
    """
    Message handler for new pull-request opened in pagure.
    Topics:
    - ``*.pagure.pull-request.new``
    - ``*.pagure.pull-request.updated``
    - ``*.pagure.pull-request.rebased``
    """
    return munch.Munch({
        'object_id': data['msg']['pullrequest']['id'],
        'object_type': 'pull-request',
        'base_project_url_path': data['msg']['pullrequest']['project']['url_path'],
        'base_clone_url_path': data['msg']['pullrequest']['project']['fullname'],
        'base_clone_url': base_url + data['msg']['pullrequest']['project']['fullname'],
        'project_url_path': data['msg']['pullrequest']['repo_from']['url_path'],
        'clone_url_path': data['msg']['pullrequest']['repo_from']['fullname'],
        'clone_url': base_url + data['msg']['pullrequest']['repo_from']['fullname'],
        'branch_from': data['msg']['pullrequest']['branch_from'],
        'branch_to': data['msg']['pullrequest']['branch'],
        'start_commit': data['msg']['pullrequest']['commit_start'],
        'end_commit': data['msg']['pullrequest']['commit_stop'],
        'user': data['msg']['pullrequest']['user']['name'],
    })


def event_info_from_push(data, base_url):
    """
    Message handler for push event in pagure.
    Topic: ``*.pagure.git.receive``
    """
    return munch.Munch({
        'object_id': data['msg']['end_commit'],
        'object_type': 'commit',
        'base_project_url_path': data['msg']['repo']['url_path'],
        'base_clone_url_path': data['msg']['repo']['fullname'],
        'base_clone_url': base_url + data['msg']['repo']['fullname'],
        'project_url_path': data['msg']['repo']['url_path'],
        'clone_url_path': data['msg']['repo']['fullname'],
        'clone_url': base_url + data['msg']['repo']['fullname'],
        'branch_from': data['msg']['branch'],
        'branch_to': data['msg']['branch'],
        'start_commit': data['msg']['start_commit'],
        'end_commit': data['msg']['end_commit'],
        # There's no better user identification of the committer.  It can be
        # normal user, or some bot.  We use this value for sandboxing so the
        # value doesn't play a security role too much -- pushed stuff should be
        # safe to build no matter what.
        'user': data['msg']['agent'],
    })


def git_compare_urls(url1, url2):
    url1 = re.sub(r'(\.git)?/*$', '', str(url1))
    url2 = re.sub(r'(\.git)?/*$', '', str(url2))
    o1 = urlparse(url1)
    o2 = urlparse(url2)
    return (o1.netloc == o2.netloc and o1.path == o2.path)


class build_on_fedmsg_loop():

    def __call__(self, message):
        pp = pprint.PrettyPrinter(width=120)

        log.debug('Parsing...')
        data = {
            'topic': message.topic,
            'msg': message.body
        }

        log.info('Got topic: {}'.format(data['topic']))
        base_url = TOPICS.get(data['topic'])
        if not base_url:
            log.error('Unknown topic {} received. Continuing.')
            return

        if re.match(r'^.*.pull-request.(new|rebased|updated)$', data['topic']):
            event_info = event_info_from_pr(data, base_url)
        elif re.match(r'^.*.pull-request.comment.added$', data['topic']):
            event_info = event_info_from_pr_comment(data, base_url)
        else:
            event_info = event_info_from_push(data, base_url)

        log.info('event_info = {}'.format(pp.pformat(event_info)))

        if not event_info:
            log.info('Received event was discarded. Continuing.')
            return

        candidates = ScmPackage.get_candidates_for_rebuild(event_info.base_clone_url)
        changed_files = set()

        if candidates:
            raw_commit_url = base_url + event_info.project_url_path + '/raw/' + event_info.start_commit
            raw_commit_text = get_repeatedly(raw_commit_url)
            changed_files |= helpers.raw_commit_changes(raw_commit_text)

            if event_info.start_commit != event_info.end_commit:
                # we want to show changes in start_commit + diff
                # start_commit..end_commit
                change_html_url = '{base_url}{project}/c/{start}..{end}'.format(
                    base_url=base_url,
                    project=event_info.project_url_path,
                    start=event_info.start_commit,
                    end=event_info.end_commit)

                change_html_text = get_repeatedly(change_html_url)
                changed_files |= helpers.pagure_html_diff_changed(change_html_text)

        log.info("changed files: {}".format(", ".join(changed_files)))

        for pkg in candidates:
            package = '{}/{}(id={})'.format(
                    pkg.package.copr.full_name,
                    pkg.package.name,
                    pkg.package.id
            )
            log.info('Considering pkg package: {}, source_json: {}'
                        .format(package, pkg.source_json_dict))

            if not pkg.copr.active_copr_chroots:
                log.info("No active chroots in this project, skipped.")
                continue

            if (git_compare_urls(pkg.clone_url, event_info.base_clone_url)
                    and (not pkg.committish or event_info.branch_to.endswith(pkg.committish))
                    and pkg.is_dir_in_commit(changed_files)):

                log.info('\t -> accepted.')

                if event_info.object_type == 'pull-request':
                    dirname = pkg.copr.name + ':pr:' + str(event_info.object_id)
                    copr_dir = CoprDirsLogic.get_or_create(pkg.copr, dirname,
                                                           trusted_caller=True)
                    update_callback = 'pagure_flag_pull_request'
                    scm_object_url = os.path.join(base_url, event_info.project_url_path,
                                                  'c', str(event_info.end_commit))
                else:
                    copr_dir = pkg.copr.main_dir
                    update_callback = 'pagure_flag_commit'
                    scm_object_url = os.path.join(base_url, event_info.base_project_url_path,
                                                  'c', str(event_info.object_id))

                if not git_compare_urls(pkg.copr.scm_repo_url, event_info.base_clone_url):
                    update_callback = ''

                source_dict_update = {
                    'clone_url': event_info.clone_url,
                    'committish': event_info.end_commit,
                }

                try:
                    build = pkg.build(
                        source_dict_update,
                        copr_dir,
                        update_callback,
                        event_info.object_type,
                        event_info.object_id,
                        scm_object_url,
                        "{}user/{}".format(base_url, event_info.user),
                    )
                    if build:
                        log.info('\t -> {}'.format(build.to_dict()))
                except Exception as e:
                    log.exception(str(e))
                    db.session.rollback()
                else:
                    db.session.commit()
            else:
                log.info('\t -> skipping.')
