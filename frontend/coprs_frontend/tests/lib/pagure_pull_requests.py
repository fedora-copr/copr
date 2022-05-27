"""
Helper methods for generating PR builds
"""

import copy

from unittest import mock

from coprs import db, models
from copr_common.enums import StatusEnum

from pagure_events import build_on_fedmsg_loop


def get_pagure_pr_event():
    return copy.deepcopy({
        "msg": {
            "agent": "test",
            "pullrequest": {
                "branch": "master",
                "branch_from": "test_PR",
                "id": 1,
                "commit_start": "78a74b02771506daf8927b3391a669cbc32ccf10",
                "commit_stop": "da3d120f2ff24fa730067735c19a0b52c8bc1a44",
                "repo_from": {
                    "fullname": "test/copr/copr",
                    "url_path": "test/copr/copr",
                },
                "project": {
                    "fullname": "test/copr/copr",
                    "url_path": "test/copr/copr",
                },
                'status': 'Open',
                "comments": [],
                'user': {
                    "fullname": "John Doe",
                    "url_path": "user/jdoe",
                    "full_url": "https://src.fedoraproject.org/user/jdoe",
                    "name": "jdoe"
                },
            }
        }
    })


class _Message:
    def __init__(self, topic, body):
        self.topic = topic
        self.body = body


class PullRequestTrigger:
    """ Trigger builds using "Pagure-like" message """
    test_object = None
    data = get_pagure_pr_event()

    def __init__(self, test_object):
        self.test_object = test_object
        self.build = build_on_fedmsg_loop()

    @staticmethod
    def _get_the_package(project, pkgname):
        return models.Package.query.filter(
            models.Package.copr_id==project.id,
            models.Package.name==pkgname,
        ).one_or_none()

    @mock.patch('pagure_events.get_repeatedly', mock.Mock())
    def build_package(self, project_name, pkgname, pr_id):
        """ Trigger a build in Copr with name """
        project = models.Copr.query.filter(
            models.Copr.name == project_name).one()

        package = self._get_the_package(project, pkgname)

        build_count = models.Build.query.count()

        if not package:
            self.test_object.api3.create_distgit_package(
                project.name,
                pkgname,
                {"webhook_rebuild": True},
            )
            db.session.commit()

        package = self._get_the_package(project, pkgname)

        data = copy.deepcopy(self.data['msg'])
        data['pullrequest']['project'] = {
            "fullname": "rpms/" + pkgname,
            "url_path": "rpms/" + pkgname,
        }
        data['pullrequest']['id'] = int(pr_id)
        message = _Message(
            'org.fedoraproject.prod.pagure.pull-request.updated',
            data,
        )
        with mock.patch('pagure_events.helpers.raw_commit_changes') as patch:
            patch.return_value = {
                'tests/integration/conftest.py @@ -28,6 +28,16 @@ def test_env(): return env',
                'tests/integration/conftest.py b/tests/integration/conftest.py index '
                '1747874..a2b81f6 100644 --- a/tests/integration/conftest.py +++'}
            self.build(message)

        builds = models.Build.query.order_by("id").all()

        build_count_new = models.Build.query.count()
        assert build_count_new == build_count + 1

        build = builds[-1] # last build

        build.source_status = StatusEnum("succeeded")
        for bch in build.build_chroots:
            bch.status = StatusEnum("succeeded")

        return build

    def build_package_with_args(self, project_name, pkgname, pr_id,
                                submitted_on=None):
        """ Trigger a build in Copr with name and additional args """
        build = self.build_package(project_name, pkgname, pr_id)
        if submitted_on is not None:
            build.submitted_on = submitted_on
        db.session.commit()
