import json

from unittest import mock, skip
import pytest

from flask_sqlalchemy import get_debug_queries

from copr_common.enums import BackendResultEnum, StatusEnum, DefaultActionPriorityEnum
from tests.coprs_test_case import CoprsTestCase, new_app_context
from coprs.logic.builds_logic import BuildsLogic
from coprs import app


class TestGetBuildTask(CoprsTestCase):

    def test_module_name_empty(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.c1.copr_chroots[0].module_toggle = ""
        r = self.tc.get("/backend/get-build-task/" + str(self.b2.id) + "-fedora-18-x86_64", headers=self.auth_header).data
        data = json.loads(r.decode("utf-8"))
        assert 'modules' not in data
        assert data["git_repo"] == "http://copr-dist-git-dev.fedorainfracloud.org/git/user1/foocopr/hello-world"

    def test_module_name_enable(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.c1.copr_chroots[0].module_toggle = "XXX"
        r = self.tc.get("/backend/get-build-task/" + str(self.b2.id) + "-fedora-18-x86_64", headers=self.auth_header).data
        data = json.loads(r.decode("utf-8"))
        assert data['modules']['toggle'] == [{'enable': 'XXX'}]

    def test_module_name_disable(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.c1.copr_chroots[0].module_toggle = "!XXX"
        r = self.tc.get("/backend/get-build-task/" + str(self.b2.id) + "-fedora-18-x86_64", headers=self.auth_header).data
        data = json.loads(r.decode("utf-8"))
        assert data['modules']['toggle'] == [{'disable': 'XXX'}]

    def test_module_name_many_modules(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.c1.copr_chroots[0].module_toggle = "XXX,!YYY,ZZZ"
        r = self.tc.get("/backend/get-build-task/" + str(self.b2.id) + "-fedora-18-x86_64", headers=self.auth_header).data
        data = json.loads(r.decode("utf-8"))
        assert data['modules']['toggle'] == [{'enable': 'XXX'}, {'disable': 'YYY'}, {'enable': 'ZZZ'}]

    def test_module_name_modules_with_spaces(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.c1.copr_chroots[0].module_toggle = "!XXX, YYY, ZZZ"
        r = self.tc.get("/backend/get-build-task/" + str(self.b2.id) + "-fedora-18-x86_64", headers=self.auth_header).data
        data = json.loads(r.decode("utf-8"))
        assert data['modules']['toggle'] == [{'disable': 'XXX'}, {'enable': 'YYY'}, {'enable': 'ZZZ'}]

class TestWaitingBuilds(CoprsTestCase):

    def test_no_pending_builds(self):
        assert b'[]' in self.tc.get(
            "/backend/pending-jobs/", headers=self.auth_header).data

    def test_pending_build_only_lists_not_started_or_ended(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        for build_chroots in [self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = StatusEnum("running")

        for build_chroot in self.b1_bc:
            build_chroot.status = StatusEnum("failed")

        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/", headers=self.auth_header)
        assert len(json.loads(r.data.decode("utf-8"))) == 5

        for build_chroot in self.b2_bc:
            build_chroot.status = StatusEnum("pending")
            self.db.session.add(build_chroot)

        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/", headers=self.auth_header)
        assert len(json.loads(r.data.decode("utf-8"))) == 5


    def test_pending_bg_build(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.b2.is_background = True
        for build_chroots in [self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 4  # pending
        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/")
        data = json.loads(r.data.decode("utf-8"))
        assert data[0]["build_id"] == 3

    def test_pending_blocked_builds(self, f_users, f_coprs, f_mock_chroots, f_builds, f_batches, f_db):
        for build in [self.b2, self.b3, self.b4]:
            build.source_status = StatusEnum("pending")

        self.b2.batch = self.batch2
        self.b3.batch = self.batch3
        self.batch3.blocked_by = self.batch2
        self.db.session.commit()

        r = self.tc.get("/backend/pending-jobs/")
        data = json.loads(r.data.decode("utf-8"))

        ids = [job["build_id"] for job in data]
        assert self.b3.id not in ids
        assert {self.b2.id, self.b4.id}.issubset(ids)

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds", "f_db")
    def test_build_jobs_performance(self):
        self.b2.source_status = StatusEnum("pending")
        self.b2.is_background = True
        for bch in self.b3_bc:
            bch.status = StatusEnum("pending")

        self.mc2.tags_raw = "foo 	 bar"
        self.db.session.commit()

        with app.app_context():
            r = self.tc.get("/backend/pending-jobs/")
            data = json.loads(r.data.decode("utf-8"))
            dq = get_debug_queries()

        # Only two queries should occur.  If you happen to see higher number
        # here, please check the get_pending_srpm_build_tasks and
        # get_pending_build_tasks methods to enhance the preloaded data.
        assert len(dq) == 2

        # No redundant data should occur in the output.  Only what BE needs.
        assert data == [{
            'build_id': 2,
            'task_id': '2',
            'background': True,
            'chroot': None,
            'project_owner': 'user1',
            'sandbox':
            'user1/foocopr--user2',
        }, {
            'build_id': 3,
            'task_id': '3-fedora-17-x86_64',
            'background': False,
            'chroot': 'fedora-17-x86_64',
            'project_owner': 'user2',
            'sandbox': 'user2/foocopr--user2',
            'tags': ['foo', 'bar'],
        }, {
            'build_id': 3,
            'task_id': '3-fedora-17-i386',
            'background': False,
            'chroot': 'fedora-17-i386',
            'project_owner': 'user2',
            'sandbox': 'user2/foocopr--user2',
            'tags': [],
        }]

# status = 0 # failure
# status = 1 # succeeded
class TestUpdateBuilds(CoprsTestCase):
    built_packages = """
{
  "packages":[
    {
      "name":"example",
      "epoch":0,
      "version":"1.0.14",
      "release":"1.fc30",
      "arch":"x86_64"
    }
  ]
}"""

    data1 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "result_dir": "bar",
     "started_on": 1390866440
   }
  ]
}"""

    data2 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "status": 1,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "results": {
       "packages":[
         {
           "name":"example",
           "epoch":0,
           "version":"1.0.14",
           "release":"1.fc30",
           "arch":"x86_64"
         }
       ]
     },
     "ended_on": 1490866440
   }
  ]
}"""

    data3 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "chroot": "fedora-18-x86_64",
     "status": 6,
     "result_dir": "bar",
     "started_on": 1390866440
   },
   {
     "id": 2,
     "copr_id": 1,
     "status": 0,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "results": {"packages": []},
     "ended_on": 1390866440
   },
   {
     "id": 123321,
     "copr_id": 1,
     "status": 0,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "results": {"packages": []},
     "ended_on": 1390866440
   },
   {
     "id": 1234321,
     "copr_id": 2,
     "chroot": "fedora-18-x86_64",
     "result_dir": "bar",
     "started_on": 1390866440
   }
  ]
}"""

    import_data1 = """
{
  "build_id": 2,
  "branch_commits": {
    "f28": "4dc32823233c0ef1aacc6f345b674d4f40a026b8"
  },
  "reponame": "test/foo"
}
"""

    def test_updating_requires_password(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         data="")
        assert b"You have to provide the correct password" in r.data

    # todo: add test for `backend/starting_build/`

    def test_update_build_ended(self, f_users, f_coprs, f_mock_chroots,
                                f_builds, f_db):
        self.db.session.commit()
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data2)
        assert json.loads(r.data.decode("utf-8"))["updated_builds_ids"] == [1]
        assert json.loads(r.data.decode("utf-8"))["non_existing_builds_ids"] == []

        updated = self.models.Build.query.filter(
            self.models.Build.id == 1).one()

        assert len(updated.build_chroots) == 1
        assert updated.build_chroots[0].status == 1
        assert updated.status == 1
        assert updated.chroots_ended_on == {'fedora-18-x86_64': 1490866440}

    def test_update_state_from_dict(self, f_users, f_fork_prepare):
        upd_dict = {'build_id': 6, 'chroot': 'srpm-builds',
                    'destdir': '/var/lib/copr/public_html/results', 'enable_net': False, 'ended_on': 1569919634,
                    'id': 6, 'source_type': 0, 'status': 0, 'submitter': 'user1', 'task_id': '6', 'timeout': 3600}
        BuildsLogic.update_state_from_dict(self.b6, upd_dict)
        updated = self.models.Build.query.filter(self.models.Build.id == 6).one()
        assert upd_dict['ended_on'] == updated.started_on

        upd_dict['started_on'] = 1569919624
        BuildsLogic.update_state_from_dict(self.b6, upd_dict)
        updated = self.models.Build.query.filter(self.models.Build.id == 6).one()
        assert upd_dict['started_on'] == updated.started_on

    def test_update_more_existent_and_non_existent_builds(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.db.session.add_all([self.b1, self.b2])
        self.db.session.commit()

        # test that import hook works
        r = self.tc.post("/backend/import-completed/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.import_data1)
        assert r.status_code == 200

        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data3)

        assert sorted(json.loads(r.data.decode("utf-8"))["updated_builds_ids"]) == [1, 2]
        assert sorted(json.loads(r.data.decode("utf-8"))["non_existing_builds_ids"]) == [
            123321, 1234321]

        started = self.models.Build.query.filter(
            self.models.Build.id == 1).first()
        assert started.chroots_started_on == {'fedora-18-x86_64': 1390866440}

        ended = self.models.Build.query.filter(
            self.models.Build.id == 2).first()
        assert ended.status == 0
        assert ended.result_dir == "00000002"
        assert ended.chroots_ended_on == {'fedora-18-x86_64': 1390866440}

    def test_build_task_canceled_waiting_build(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.db.session.add(self.b3)
        self.db.session.commit()

        r = self.tc.post("/backend/build-tasks/canceled/{}/".format(self.b3.id),
                         content_type="application/json",
                         headers=self.auth_header,
                         data=json.dumps(False))
        assert r.status_code == 200
        assert json.loads(r.data.decode("utf-8")) == "success"

        build = self.models.Build.query.filter(self.models.Build.id == 3).one()
        assert build.source_status == StatusEnum("canceled")

    def test_build_task_canceled_running_build(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.b4.build_chroots.pop()
        self.b4.build_chroots[0].status = StatusEnum("running")
        self.db.session.add(self.b4)
        self.db.session.commit()

        r = self.tc.post("/backend/build-tasks/canceled/{}/".format(self.b4.id),
                         content_type="application/json",
                         headers=self.auth_header,
                         data=json.dumps(True))

        assert r.status_code == 200
        assert json.loads(r.data.decode("utf-8")) == "success"

        build = self.models.Build.query.filter(self.models.Build.id == 4).one()
        assert build.canceled == False
        assert build.build_chroots[0].status == StatusEnum("running")

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds", "f_db")
    def test_build_task_canceled_deleted_build(self):

        self.models.Build.query.filter_by(id=self.b3.id).delete()
        self.db.session.commit()

        r = self.tc.post("/backend/build-tasks/canceled/{}/".format(self.b3.id),
                         content_type="application/json",
                         headers=self.auth_header,
                         data=json.dumps(False))
        assert r.status_code == 200
        assert json.loads(r.data.decode("utf-8")) == "success"

        cancel_request_table = self.models.CancelRequest.query.all()
        assert len(cancel_request_table) == 0


class TestWaitingActions(CoprsTestCase):

    def test_no_waiting_actions(self):
        assert b'null' in self.tc.get(
            "/backend/pending-action/", headers=self.auth_header).data

    def test_waiting_actions_only_lists_not_started_or_ended(
            self, f_users, f_coprs, f_actions, f_db):

        for a in [self.delete_action, self.cancel_build_action]:
            a.result = BackendResultEnum("success")

        self.db.session.commit()

        r = self.tc.get("/backend/pending-action/", headers=self.auth_header)
        assert json.loads(r.data.decode("utf-8")) == None

        for a in [self.delete_action]:
            a.result = BackendResultEnum("waiting")
            self.db.session.add(a)

        self.db.session.commit()
        r = self.tc.get("/backend/pending-action/", headers=self.auth_header)
        assert json.loads(r.data.decode("utf-8")) != None

    @new_app_context
    def test_pending_actions_list(self, f_users, f_coprs, f_actions, f_db):
        r = self.tc.get("/backend/pending-actions/", headers=self.auth_header)
        actions = json.loads(r.data.decode("utf-8"))
        assert actions == [
            {'id': 1, 'priority': DefaultActionPriorityEnum("delete")},
            {'id': 2, 'priority': DefaultActionPriorityEnum("cancel_build")}
        ]

        self.delete_action.result = BackendResultEnum("success")
        self.db.session.add(self.delete_action)
        self.db.session.commit()

        r = self.tc.get("/backend/pending-actions/", headers=self.auth_header)
        actions = json.loads(r.data.decode("utf-8"))
        assert len(actions) == 1

    @new_app_context
    def test_get_action_succeeded(self, f_users, f_coprs, f_actions, f_db):
        r = self.tc.get("/backend/action/1/",
                        headers=self.auth_header)
        data = json.loads(r.data.decode('utf-8'))

        # make one succeeded
        self.delete_action.result = BackendResultEnum("success")
        self.db.session.add(self.delete_action)
        self.db.session.commit()

        r = self.tc.get("/backend/action/1/",
                        headers=self.auth_header)
        data_success = json.loads(r.data.decode('utf-8'))
        assert data != data_success
        data_success.update({'result': 0})
        assert data == data_success

        # make one failed
        self.delete_action.result = BackendResultEnum("failure")
        self.db.session.add(self.delete_action)
        self.db.session.commit()

        r = self.tc.get("/backend/action/1/",
                        headers=self.auth_header)
        data_fail = json.loads(r.data.decode('utf-8'))
        assert data != data_fail
        data.update({'result': 2})
        assert data == data_fail


class TestUpdateActions(CoprsTestCase):
    data1 = """
{
  "actions":[
    {
      "id": 1,
      "result": 1,
      "message": "no problem",
      "ended_on": 1390866440
    }
  ]
}"""
    data2 = """
{
  "actions":[
    {
      "id": 1,
      "result": 1,
      "message": null
    },
    {
      "id": 2,
      "result": 2,
      "message": "problem!"
    },
    {
      "id": 100,
      "result": 123,
      "message": "wheeeee!"
    }
  ]
}"""

    @mock.patch('coprs.logic.actions_logic.time.time')
    def test_update_one_action(self, mc_time, f_users, f_coprs, f_actions, f_db):
        mc_time.return_value = 1390866440
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data1)
        assert json.loads(r.data.decode("utf-8"))["updated_actions_ids"] == [1]
        assert json.loads(r.data.decode("utf-8"))["non_existing_actions_ids"] == []

        updated = self.models.Action.query.filter(
            self.models.Action.id == 1).first()
        assert updated.result == 1
        assert updated.message == "no problem"
        assert updated.ended_on == 1390866440


    @mock.patch('coprs.logic.actions_logic.time.time')
    def test_update_more_existent_and_non_existent_actions(self, mc_time, f_users,
                                                           f_coprs, f_actions,
                                                           f_db):
        mc_time.return_value = 1390866440
        r = self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data2)
        assert sorted(json.loads(r.data.decode("utf-8"))["updated_actions_ids"]) == [1, 2]
        assert json.loads(r.data.decode("utf-8"))["non_existing_actions_ids"] == [100]

        updated = self.models.Action.query.filter(
            self.models.Action.id == 1).first()
        assert updated.result == 1
        assert updated.message is None
        assert updated.ended_on == 1390866440

        updated2 = self.models.Action.query.filter(
            self.models.Action.id == 2).first()
        assert updated2.result == 2
        assert updated2.message == "problem!"
        assert updated2.ended_on == 1390866440


class TestImportingBuilds(CoprsTestCase):
    data = """
{
  "builds":[
    {
      "id": 1,
      "task_id": 1,
      "srpm_url": "http://foo",
      "status": 1,
      "pkg_name": "foo",
      "pkg_version": 1
    },
    {
      "id": 2,
      "task_id": 2,
      "srpm_url": "http://bar",
      "status": 1,
      "pkg_name": "bar",
      "pkg_version": 2
    }
  ]
}"""

    def test_bg_priority_in_queue(self, f_users, f_coprs, f_mock_chroots, f_db):
        BuildsLogic.create_new_from_url(self.u1, self.c1, "foo", background=True)
        BuildsLogic.create_new_from_url(self.u1, self.c1, "bar")

        self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data)

        r = self.tc.get("/backend/importing/")
        data = json.loads(r.data.decode("utf-8"))

        # Make sure we set the `background` key, but ignore the task order.
        # Tasks will be prioritized appropriately on DistGit
        assert data[0]["srpm_url"] == "http://foo"
        assert data[0]["background"] is True
        assert data[1]["srpm_url"] == "http://bar"
        assert data[1]["background"] is False

    def test_importing_queue_multiple_bg(self, f_users, f_coprs, f_mock_chroots, f_db):
        BuildsLogic.create_new_from_url(self.u1, self.c1, "foo", background=True)
        BuildsLogic.create_new_from_url(self.u1, self.c1, "bar", background=True)

        self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data)

        r = self.tc.get("/backend/importing/")
        data = json.loads(r.data.decode("utf-8"))
        assert data[0]["srpm_url"] == "http://foo"
        assert data[1]["srpm_url"] == "http://bar"
