import json
from unittest import mock

import pytest

from coprs import models, app, db
from check_for_anitya_version_updates import main, is_stable_release
from tests.coprs_test_case import (CoprsTestCase, TransactionDecorator)

def run_patched_main(args, messages):
    with mock.patch("check_for_anitya_version_updates.sys.argv", args):
        with mock.patch("check_for_anitya_version_updates.log", app.logger):
            with mock.patch("check_for_anitya_version_updates._get_json") as get_json:
                get_json.return_value = messages
                return main()


class TestAnitya(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_users_api", "f_mock_chroots", "f_db")
    def test_pypi(self):
        contents = self.load_test_data_file("anytia.json")
        messages = json.loads(contents)
        chroots = ["fedora-rawhide-i386"]

        # Loop to generate projects with single (finished) build
        for project in ["foo", "deleted", "inprogress", "inprogress-match",
                        "inprogress-older"]:
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

        # Submit one build manually (not finished).  This must not be
        # re-submitted via anitya automation.  This package has no version info
        # in json, yet.
        self.api3.rebuild_package("inprogress", "python-umap-pytorch")

        # Submit another build (not finished).  This one though has the
        # pypi_package_version field specified (could be submitted by anitya).
        resp = self.api3.rebuild_package("inprogress-match", "python-umap-pytorch")
        build = self.db.session.get(models.Build, int(resp.json["id"]))
        build.source_json = json.dumps({"pypi_package_version": "0.0.5"})
        db.session.commit()

        # Submit yet another build (not finished).  This one though has the
        # pypi_package_version field specified, and is older so we want to
        # re-build).
        resp = self.api3.rebuild_package("inprogress-older", "python-umap-pytorch")
        build = self.db.session.get(models.Build, int(resp.json["id"]))
        build.source_json = json.dumps({"pypi_package_version": "0.0.4"})
        db.session.commit()

        # Delete one project.  No more builds in that.
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
        assert len(builds) == 11
        for build in builds:
            if build.state == "succeeded":
                continue  # the first two builds

            copr = build.copr.full_name
            source_json = json.loads(build.source_json)
            if copr == "user1/foo":
                # Updated package, 0.0.4 => 0.0.5
                assert source_json == {
                    'pypi_package_name': 'umap-pytorch',
                    'pypi_package_version': '0.0.5',
                    'python_versions': ['3'],
                    'spec_generator': 'pyp2rpm',
                    'spec_template': '',
                }
            elif copr == "user1/bar":
                # package never built before
                assert json.loads(build.source_json) == {
                    'pypi_package_name': 'zod',
                    'pypi_package_version': '0.0.13',
                    'python_versions': ['3'],
                    'spec_generator': 'pyp2spec',
                    'spec_template': '',
                }
            elif copr == "user1/inprogress":
                # manually submitted build, blocks further anitya rebuilds
                assert json.loads(build.source_json) == {
                    'pypi_package_name': 'umap-pytorch',
                    'pypi_package_version': None,
                    'python_versions': ['3'],
                    'spec_generator': 'pyp2rpm',
                    'spec_template': '',
                }
            elif copr == "user1/inprogress-match":
                # build submitted by anytia, with the same version
                assert json.loads(build.source_json) == {
                    'pypi_package_version': "0.0.5",
                }
            elif copr == "user1/inprogress-older":
                # build submitted by anytia, with the same version
                if build.id == 8:
                    assert json.loads(build.source_json) == {
                        'pypi_package_version': "0.0.4",
                    }
                else:
                    assert json.loads(build.source_json) == {
                        'pypi_package_name': 'umap-pytorch',
                        'pypi_package_version': '0.0.5',
                        'python_versions': ['3'],
                        'spec_generator': 'pyp2rpm',
                        'spec_template': '',
                    }
            else:
                # No more builds!
                assert False


def test_pre_release_matcher():
    assert not is_stable_release("1.7.1.31122022.post35")
    assert not is_stable_release("1.7.1.31122022.post35")
    assert not is_stable_release("0.17.0a1")
    assert not is_stable_release("1.9b2")
    assert is_stable_release("1")
    assert is_stable_release("1.1")
    assert is_stable_release("1.2.3")
    assert is_stable_release("112312")
