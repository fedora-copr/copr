# -*- encoding: utf-8 -*-

import json
import os
import tempfile
import time
from unittest import mock

import pytest

from sqlalchemy.orm.exc import NoResultFound
from coprs import models
from coprs.request import NAMED_FILE_FROM_BYTES

from copr_common.enums import StatusEnum
from coprs.exceptions import (ActionInProgressException,
                              InsufficientRightsException,
                              MalformedArgumentException,
                              BadRequest,
                              InsufficientStorage)

from coprs.logic.actions_logic import ActionsLogic
from coprs.logic.builds_logic import (
    BuildsLogic,
)

from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestBuildsLogic(CoprsTestCase):
    # pylint: disable=too-many-public-methods

    data = """
{
  "builds":[
    {
      "id": 5,
      "task_id": 5,
      "srpm_url": "http://foo",
      "status": 1,
      "pkg_name": "foo",
      "pkg_version": 1
    }
  ]
}"""

    def test_add_only_adds_active_chroots(self, f_users, f_coprs, f_builds,
                                          f_mock_chroots, f_db):

        self.mc2.is_active = False
        self.db.session.commit()
        b = BuildsLogic.add(self.u2, "blah", self.c2)
        self.db.session.commit()
        build_id = b.id
        expected_name = self.mc3.name
        assert len(b.chroots) == 0

        self.tc.post("/backend/update/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=self.data)

        b = BuildsLogic.get(build_id).first()
        assert len(b.chroots) == 1
        assert b.chroots[0].name == expected_name

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_build_still_active_chroots(self):
        builds = self.models.Build.query.all()
        assert len(builds[2].chroots_still_active) == 2

        # disable f17-x86_64
        self.mc2.is_active = False
        self.db.session.commit()

        builds = self.models.Build.query.all()
        assert len(builds[2].chroots_still_active) == 1
        assert builds[2].chroots_still_active == [self.mc3]

    def test_add_raises_if_copr_has_unfinished_actions(self, f_users, f_coprs,
                                                       f_actions, f_db):

        with pytest.raises(ActionInProgressException):
            b = BuildsLogic.add(self.u1, "blah", self.c1)
        self.db.session.rollback()

    def test_add_assigns_params_correctly(self, f_users, f_coprs,
                                          f_mock_chroots, f_db):

        params = dict(
            user=self.u1,
            pkgs="blah",
            copr=self.c1,
            repos="repos",
            timeout=5000)

        b = BuildsLogic.add(**params)
        for k, v in params.items():
            assert getattr(b, k) == v

    def test_add_error_on_multiply_src(self, f_users, f_coprs,
                                          f_mock_chroots, f_db):

        params = dict(
            user=self.u1,
            pkgs="blah blah",
            copr=self.c1,
            repos="repos",
            timeout=5000)

        with pytest.raises(MalformedArgumentException):
            BuildsLogic.add(**params)

    """get_monitor_data output changed
    def test_monitor_logic(self, f_users, f_coprs, f_builds, f_mock_chroots_many, f_build_few_chroots, f_db):
        copr = self.c1
        md = BuildsMonitorLogic.get_monitor_data(copr)
        assert len(md) == 1
        assert len(md[0]["build_chroots"]) == 15
    """

    def test_build_queue_1(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_build_importing_queue().all()
        assert len(data) == 2

    def test_build_queue_2(self, f_users, f_coprs, f_mock_chroots, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_build_importing_queue().all()
        assert len(data) == 0

    def test_build_queue_3(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for build_chroots in [self.b1_bc, self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 0
        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()
        assert len(data) == 0

    def test_build_queue_4(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        """ test that pending/running tasks are returned as pending """
        counter = 0
        for build_chroots in [self.b1_bc, self.b2_bc]:
            for build_chroot in build_chroots:
                build_chroot.ended_on = None
                build_chroot.status = StatusEnum("starting") if counter % 2 else StatusEnum("running")
                counter += 1
        for build_chroots in [self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = StatusEnum("failed")
                build_chroot.ended_on = None

        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks(data_type="for_backend").all()

        assert len(data) == 2
        assert set([data[0], data[1]]) == set([self.b1_bc[0], self.b2_bc[0]])

    def test_build_queue_5(self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for build_chroots in [self.b2_bc, self.b3_bc, self.b4_bc]:
            for build_chroot in build_chroots:
                build_chroot.status = 4 # pending
        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()
        assert len(data) == 5

    def test_build_queue_6(self, f_users, f_coprs, f_mock_chroots, f_db):
        self.db.session.commit()
        data = BuildsLogic.get_pending_build_tasks().all()
        assert len(data) == 0

    @staticmethod
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds",
                             "f_db")
    def test_build_queue_7():
        assert len(BuildsLogic.get_pending_srpm_build_tasks().all()) == 0
        models.Build.query.get(1).source_status = StatusEnum("pending")
        models.Build.query.get(2).source_status = StatusEnum("starting")
        models.Build.query.get(3).source_status = StatusEnum("running")
        assert len(BuildsLogic.get_pending_srpm_build_tasks().all()) == 1
        assert len(BuildsLogic.get_pending_srpm_build_tasks(data_type="for_backend").all()) == 3

    def test_delete_build_exceptions(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):
        for bc in self.b4_bc:
            bc.status = StatusEnum("succeeded")
            bc.ended_on = time.time()
        self.u1.admin = False

        self.db.session.add_all(self.b4_bc)
        self.db.session.add(self.b4)
        self.db.session.add(self.u1)
        self.db.session.commit()
        with pytest.raises(InsufficientRightsException):
            BuildsLogic.delete_build(self.u1, self.b4)

        self.b1_bc[0].status = StatusEnum("running")
        self.db.session.add(self.b1_bc[0])
        self.db.session.commit()
        with pytest.raises(ActionInProgressException):
            BuildsLogic.delete_build(self.u1, self.b1)

        self.copr_persistent = models.Copr(name=u"persistent_copr", user=self.u2, persistent=True)
        self.copr_dir = models.CoprDir(name="persistent_copr", main=True, copr=self.copr_persistent)
        self.build_persistent = models.Build(
            copr=self.copr_persistent, copr_dir=self.copr_dir,
            package=self.p2, user=self.u2, submitted_on=100)
        with pytest.raises(InsufficientRightsException):
            BuildsLogic.delete_build(self.u2, self.build_persistent)


    def test_delete_build_as_admin(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.b4.pkgs = "http://example.com/copr-keygen-1.58-1.fc20.src.rpm"
        expected_dir = self.b4.result_dir
        for bc in self.b4_bc:
            bc.status = StatusEnum("succeeded")
            bc.ended_on = time.time()

        self.u1.admin = True

        self.db.session.add_all(self.b4_bc)
        self.db.session.add(self.b4)
        self.db.session.add(self.u1)
        self.db.session.commit()

        expected_chroots_to_delete = set()
        for bchroot in self.b4_bc:
            expected_chroots_to_delete.add(bchroot.name)

        assert len(ActionsLogic.get_many().all()) == 0
        self.b4.copr.appstream = True
        BuildsLogic.delete_build(self.u1, self.b4)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 1
        action = ActionsLogic.get_many().one()

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b4.id).one()

    def test_delete_build_no_resultdir(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.b1.pkgs = "http://example.com/copr-keygen-1.58-1.fc20.src.rpm"
        expected_dir = self.b1.result_dir
        self.db.session.add(self.b1)
        bc = self.b1_bc[0]
        bc.result_dir = ''
        self.db.session.add(bc)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 0
        self.b1.copr.appstream = True
        BuildsLogic.delete_build(self.u1, self.b1)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 1
        action = ActionsLogic.get_many().one()
        delete_data = json.loads(action.data)
        # doesn't contain 'fedora-18-x86_64': ['bar']!
        assert delete_data['chroot_builddirs'] == {'srpm-builds': ['bar']}

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b1.id).one()

    def test_delete_mulitple_builds_no_resultdir(
            self, f_users, f_coprs, f_pr_build, f_db):

        self.b1.pkgs = "http://example.com/copr-keygen-1.58-1.fc20.src.rpm"
        expected_dir = self.b1.result_dir
        self.db.session.add(self.b1)
        bc = self.b1_bc[0]
        bc.result_dir = ''

        # one more finished build
        first = True
        for bchroot in self.b2_bc:
            if first:
                first = False
                bchroot.result_dir = ''
            bchroot.status = StatusEnum('failed')
            self.db.session.add(bchroot)

        self.db.session.add(bc)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 0
        BuildsLogic.delete_builds(self.u1, [self.b1.id, self.b2.id, self.b_pr.id])
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 1
        action = ActionsLogic.get_many().one()
        delete_data = json.loads(action.data)

        # doesn't contain 'fedora-18-x86_64': ['bar']!
        assert delete_data == {
            'appstream': True,
            'ownername': 'user1',
            'projectname': 'foocopr',
            'project_dirnames': {
                'foocopr': {
                    'srpm-builds': ['bar', '00000002'],
                    # 'fedora-18-x86_64': ['bar'] # this has result_dir=''
                },
                'foocopr:PR': {
                    'srpm-builds': ['0000PR'],
                    'fedora-17-x86_64': ['0000PR-pr-package'],
                }
            },
            'build_ids': [1, 2, 5]
        }

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b1.id).one()

    def test_delete_build_basic(
            self, f_users, f_coprs, f_mock_chroots, f_builds, f_db):

        self.b1.pkgs = "http://example.com/copr-keygen-1.58-1.fc20.src.rpm"
        expected_dir = self.b1.result_dir
        self.db.session.add(self.b1)
        self.db.session.commit()

        expected_chroots_to_delete = set()
        for bchroot in self.b1_bc:
            expected_chroots_to_delete.add(bchroot.name)

        assert len(ActionsLogic.get_many().all()) == 0
        self.b1.copr.appstream = True
        BuildsLogic.delete_build(self.u1, self.b1)
        self.db.session.commit()

        assert len(ActionsLogic.get_many().all()) == 1
        action = ActionsLogic.get_many().one()
        delete_data = json.loads(action.data)
        assert delete_data['chroot_builddirs'] == {'srpm-builds': ['bar'], 'fedora-18-x86_64': ['bar']}

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b1.id).one()

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds", "f_db")
    def test_delete_multiple_builds(self):
        """
        Test deleting multiple builds at once.
        """
        for build_chroot in self.b4_bc:
            build_chroot.status = StatusEnum("succeeded")

        build_ids = [self.b1.id, self.b2.id, self.b3.id, self.b4.id, 1234]
        with pytest.raises(BadRequest) as err_msg:
            BuildsLogic.delete_builds(self.u2, build_ids)

        msg1 = "Build(s) {0} are still running".format(self.b3.id)
        msg2 = "Build(s) 1234 don't exist"
        msg3 = ("You don't have permissions to delete build(s) {0}, {1}"
                .format(self.b1.id, self.b2.id))

        for msg in [msg1, msg2, msg3]:
            assert msg in str(err_msg.value)

        for build_id in [self.b1.id, self.b2.id, self.b3.id, self.b4.id]:
            BuildsLogic.get(build_id).one()

        build_ids = [self.b1.id, self.b4.id]
        with pytest.raises(BadRequest) as err_msg:
            BuildsLogic.delete_builds(self.u1, build_ids)
        assert "Can not delete builds from more project" in str(err_msg.value)

        self.b3.source_status = StatusEnum("failed")
        build_ids = [self.b3.id, self.b4.id]
        BuildsLogic.delete_builds(self.u2, build_ids)

        assert len(ActionsLogic.get_many().all()) == 1

        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b3.id).one()
        with pytest.raises(NoResultFound):
            BuildsLogic.get(self.b4.id).one()

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_builds")
    def test_resubmit_build_inherit_git_hash(self):
        orig_git_hash = self.b1.build_chroots[0].git_hash
        self.b1.source_type = 2  # builds from upload should inherit the git hash
        new_build = BuildsLogic.create_new_from_other_build(self.u1, self.c1, self.b1)
        new_git_hash = new_build.build_chroots[0].git_hash
        assert orig_git_hash == new_git_hash

    def test_mark_as_failed(self, f_users, f_coprs, f_mock_chroots, f_builds):
        self.b1.source_status = StatusEnum("succeeded")
        self.db.session.commit()
        BuildsLogic.mark_as_failed(self.b1.id)
        BuildsLogic.mark_as_failed(self.b3.id)

        assert self.b1.status == StatusEnum("succeeded")
        assert self.b3.status == StatusEnum("failed")
        assert type(BuildsLogic.mark_as_failed(self.b3.id)) == models.Build

    def test_build_garbage_collector_works(self, f_users, f_coprs,
            f_mock_chroots, f_builds, f_db):

        assert len(self.db.session.query(models.Build).all()) == 4

        p = models.Package.query.filter_by(name='whatsupthere-world').first()
        p.max_builds = 1
        self.db.session.add(p)

        assert len(models.Package.query.all()) == 3
        BuildsLogic.clean_old_builds()

        # we can not delete not-yet finished builds!
        assert len(self.db.session.query(models.Build).all()) == 4

        self.b3.copr.appstream = True
        for bch in self.b3.build_chroots:
            bch.status = StatusEnum('succeeded')
            self.db.session.add(bch)

        assert len(self.db.session.query(models.Build).all()) == 4
        BuildsLogic.clean_old_builds()
        assert len(self.db.session.query(models.Build).all()) == 3

    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_no_active_chroot(self):
        self.c1.copr_chroots.clear()
        self.db.session.commit()
        with pytest.raises(BadRequest) as error:
            BuildsLogic.create_new(self.u1, self.c1, 0, '{}')

        assert "has no active chroots" in str(error.value)
        assert len(self.c1.active_copr_chroots) == 0

    @mock.patch('coprs.logic.builds_logic.save_form_file_field_to')
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_mock_chroots", "f_db")
    def test_create_new_from_upload_no_space_left(self, save_form_patch):
        save_form_patch.side_effect = OSError("[Errno 28] No space left on device")

        with pytest.raises(InsufficientStorage) as error:
            BuildsLogic.create_new_from_upload(self.u1, self.c1, None,
                                               "fake.src.rpm",
                                               chroot_names=["fedora-18-x86_64"],
                                               copr_dirname=None)
        assert "Can not create storage directory for uploaded file" in str(error.value)
        assert "[Errno 28] No space left on device" in str(error.value)

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_package_assigned_to_build_initially(self):
        self.web_ui.new_project("test", ["fedora-rawhide-i386"],
                                bootstrap="on")
        self.web_ui.create_distgit_package("test", "tar")
        self.api3.rebuild_package("test", "tar")
        build = models.Build.query.get(1)
        assert build.package.name == "tar"

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_rebuild_all_packages(self):
        self.web_ui.new_project("test", ["fedora-rawhide-i386"],
                                bootstrap="on")
        self.web_ui.create_distgit_package("test", "tar")
        self.web_ui.create_distgit_package("test", "cpio")
        copr = models.Copr.query.get(1)
        self.web_ui.rebuild_all_packages(copr.id)

        builds = models.Build.query.all()
        assert len(builds) == 2
        assert {b.package.name for b in builds} == {"tar", "cpio"}

    @TransactionDecorator("u2")
    @pytest.mark.usefixtures("f_hook_package", "f_users_api", "f_db")
    def test_package_rebuild_permission_error(self):

        # create a package and submit a build
        result = self.api3.rebuild_package("foocopr", "hook-package",
                                           project_ownername="user1")
        assert result.json == {'error': "You don't have permissions to build in this copr."}
        assert result.status_code == 403


    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_package_not_updated_after_source_ready(self):
        # create a package and submit a build
        self.web_ui.new_project("test", ["fedora-rawhide-i386"])
        self.web_ui.create_distgit_package("test", "copr-cli")
        self.api3.rebuild_package("test", "copr-cli")

        build = models.Build.query.get(1)
        assert build.status == StatusEnum("pending")

        form_data = {
            "builds": [{
                "id": 1,
                "task_id": "1",
                "srpm_url": "http://foo",
                "status": 1,
                "pkg_name": "foo",  # not a 'copr-cli'!
                "pkg_version": 1
            }],
        }

        self.backend.update(form_data)

        importing = self.backend.importing_queue()
        assert len(importing) == 1
        assert importing[0]['pkg_name'] == "copr-cli"

        build = models.Build.query.get(1)
        assert build.status == StatusEnum("importing")
        assert build.package.name == "copr-cli"

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_package_set_when_source_ready(self):
        self.web_ui.new_project("test", ["fedora-rawhide-i386"])
        self.web_ui.submit_url_build("test")

        build = models.Build.query.get(1)
        assert len(build.build_chroots) == 0
        assert build.source_status == StatusEnum("pending")
        assert build.package is None

        # define the package name to foo
        form_data = {
            "builds": [{
                "id": 1,
                "task_id": "1",
                "srpm_url": "http://foo",
                "status": 1,
                "pkg_name": "foo",  # not a 'copr-cli'!
                "pkg_version": 1
            }],
        }

        self.backend.update(form_data)
        build = models.Build.query.get(1)
        assert len(build.build_chroots) == 1
        assert build.source_status == StatusEnum("importing")
        assert build.package.name == "foo"

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    # Call SpooledTemporaryFile twice (once in memory, once in file), and
    # NamedTemporaryFile once.
    @pytest.mark.parametrize("kbytes", [100, 1024, 100*1024])
    def test_srpm_upload(self, kbytes):
        self.web_ui.new_project("test", ["fedora-rawhide-i386"])

        srpm_base = "test.src.rpm"
        workdir = os.path.dirname(__file__)
        srpm = os.path.join(workdir, srpm_base)
        with open(srpm, "w", encoding="utf-8") as fd:
            string = "x"*1024*kbytes
            fd.write(string)

        not_patched = tempfile.NamedTemporaryFile
        with mock.patch("coprs.request.tempfile.NamedTemporaryFile",
                        wraps=not_patched) as patch:
            resp = self.api3.submit_uploaded_build("test", srpm)
            exp_count = 1 if kbytes*1024 > NAMED_FILE_FROM_BYTES else 0
            assert patch.call_count == exp_count

        assert resp.status_code == 200
        # url = https://copr.stg.fedoraproject.org/tmp/tmpf_3w8r9i/test.src.rpm'
        url = json.loads(resp.data)["source_package"]["url"]
        tmpdir = url.split("/")[-2]
        storage = os.path.join(self.app.config["STORAGE_DIR"], tmpdir, srpm_base)
        stat = os.stat(storage)
        assert stat.st_size == 1024*kbytes
        assert stat.st_nlink == 1

    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("fail", [False, True])
    def test_temporary_data_removed(self, fail):
        self.web_ui.new_project("test", ["fedora-rawhide-i386"])
        content = "content"
        filename = "fake.src.rpm"
        def save_field(_field, file_path):
            assert file_path.endswith(filename)
            with open(file_path, "w", encoding="utf-8") as fd:
                fd.write(content)

        user = models.User.query.get(1)
        copr = models.Copr.query.first()

        with mock.patch("coprs.logic.builds_logic.save_form_file_field_to",
                        new=save_field):
            build = BuildsLogic.create_new_from_upload(
                user, copr, None, os.path.basename(filename),
                chroot_names=["fedora-18-x86_64"],
                copr_dirname=None)

        source_dict = build.source_json_dict
        storage = os.path.join(self.app.config["STORAGE_DIR"], source_dict["tmp"])
        with open(os.path.join(storage, filename), "r") as fd:
            assert fd.readlines() == [content]
        self.db.session.commit()
        assert os.path.exists(storage)

        form_data = {
            "builds": [{
                "id": 1,
                "task_id": "1",
                "srpm_url": "http://foo",
                "status": 0 if fail else 1,
                "pkg_name": "foo",  # not a 'copr-cli'!
                "pkg_version": 1
            }],
        }

        self.backend.update(form_data)
        build = models.Build.query.get(1)
        assert build.source_state == "failed" if fail else "importing"

        # Removed upon failure, otherwise exists!
        assert os.path.exists(storage) is not fail

        if fail:
            # nothing is imported in this case, nothing to test
            return

        # test that import hook works
        r = self.tc.post("/backend/import-completed/",
                         content_type="application/json",
                         headers=self.auth_header,
                         data=json.dumps({
                            "build_id": 1,
                            "branch_commits": {
                                "master": "4dc32823233c0ef1aacc6f345b674d4f40a026b8"
                            },
                            "reponame": "test/foo"
                        }))
        assert r.status_code == 200
        build = models.Build.query.get(1)
        assert build.source_state == "succeeded"
        assert not os.path.exists(storage)
