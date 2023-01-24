import json
from unittest import mock

import pytest

from coprs import models, app, db
from check_for_anitya_version_updates import main
from tests.coprs_test_case import (CoprsTestCase, TransactionDecorator)

@mock.patch("check_for_anitya_version_updates.run_cmd", mock.MagicMock())
def run_patched_main(args, messages):
    with mock.patch("check_for_anitya_version_updates.sys.argv", args):
        with mock.patch("check_for_anitya_version_updates.log", app.logger):
            with mock.patch("check_for_anitya_version_updates.to_json") as to_json:
                to_json.return_value = messages
                return main()


class TestAnitya(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_pypi(self):
        contents = self.load_test_data_file("anytia.json")
        messages = json.loads(contents)
        chroots = ["fedora-rawhide-i386"]
        for project in ["foo", "deleted"]:
            self.api3.new_project(project, chroots)
            self.api3.create_pypi_package(
                project, "umap-pytorch",
                options={
                    "webhook_rebuild": True,
                    "spec_generator": "pyp2rpm",
                },
            )
            # This is not going to be rebuilt, the update is 2.1.7rc1
            self.api3.create_pypi_package(
                project, "wmagent-devtools",
                options={
                    "webhook_rebuild": True,
                },
            )
            # create and build 1 and 2, and since the package is updated
            # in pypi -> we'll get bar/python-umap-pytorch rebuild
            self.rebuild_package_and_finish(project, "python-umap-pytorch",
                                            pkg_version="0.0.4")

        delete_it = models.Copr.query.filter(models.Copr.name=="deleted").one()
        delete_it.deleted = True
        db.session.commit()

        # This package has no build, just a definition - and should get it's
        # first build.
        self.api3.new_project("bar", chroots)
        self.api3.create_pypi_package("bar", "zod",
                                      options={"webhook_rebuild": True})

        run_patched_main(["anitya", "--backend", "pypi", "--delta", "100"], messages)

        builds = models.Build.query.all()
        assert len(builds) == 4
        for build in builds:
            if build.state == "succeeded":
                continue  # the first two builds

            copr = build.copr.full_name
            source_json = json.loads(build.source_json)
            if copr == "user1/foo":
                assert source_json == {
                    'pypi_package_name': 'umap-pytorch',
                    'pypi_package_version': '0.0.5',
                    'python_versions': ['3'],
                    'spec_generator': 'pyp2rpm',
                    'spec_template': '',
                }
            elif copr == "user1/bar":
                assert json.loads(build.source_json) == {
                    'pypi_package_name': 'zod',
                    'pypi_package_version': '0.0.13',
                    'python_versions': ['3'],
                    'spec_generator': 'pyp2spec',
                    'spec_template': '',
                }
            else:
                assert False
