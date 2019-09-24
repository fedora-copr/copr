# coding: utf-8
import six
import json
from copr.client_v2.net_client import ResponseWrapper

if six.PY3:
    from unittest.mock import MagicMock
else:
    from mock import MagicMock

import pytest

from copr.client_v2.handlers import ProjectHandle


class TestHandleBase(object):
    def setup_method(self, method):
        self.nc = MagicMock()
        self.client = MagicMock()

        self.root_url = "http://example.com"
        self.response = MagicMock()

        self.root_json = {
            "_links": {
                "mock_chroots": {
                    "href": "/api_2/mock_chroots"
                },
                "self": {
                    "href": "/api_2/"
                },
                "projects": {
                    "href": "/api_2/projects"
                },
                "builds": {
                    "href": "/api_2/builds"
                },
                "build_tasks": {
                    "href": "/api_2/build_tasks"
                }
            }
        }

    def get_href(self, name):
        return self.root_json["_links"][name]["href"]

    @pytest.fixture
    def project_handle(self):
        return ProjectHandle(self.client, self.nc, self.root_url,
                             self.get_href("projects"))

    def make_response(self, json_string, status=200, headers=None):
        response = MagicMock()
        response.status_code = status
        response.headers = headers or dict()
        response.content = json_string
        return ResponseWrapper(response)


class TestProjectHandle(TestHandleBase):
    project_1 = """{
        "project": {
            "description": "A simple KDE respin",
            "disable_createrepo": false,
            "repos": [],
            "contact": null,
            "owner": "jmiahman",
            "build_enable_net": true,
            "instructions": "",
            "homepage": null,
            "id": 2482,
            "name": "Synergy-Linux"
        },
        "project_chroots": [
            {
                "chroot": {
                    "comps": null,
                    "comps_len": 0,
                    "buildroot_pkgs": [],
                    "name": "fedora-19-x86_64",
                    "comps_name": null
                },
                "_links": null
            }
        ],
        "project_builds": [
            {
                "_links": null,
                "build": {
                    "enable_net": true,
                    "source_metadata": {
                        "url": "http://miroslav.suchy.cz/copr/copr-ping-1-1.fc20.src.rpm"
                    },
                    "submitted_on": 1422379448,
                    "repos": [],
                    "results": "https://copr-be.cloud.fedoraproject.org/results/jmiahman/Synergy-Linux/",
                    "started_on": 1422379466,
                    "source_type": 1,
                    "state": "succeeded",
                    "source_json": "{\\"url\\": \\"http://dl.kororaproject.org/pub/korora/releases/21/source/korora-welcome-21.6-1.fc21.src.rpm\\"}",
                    "ended_on": 1422379584,
                    "timeout": 21600,
                    "pkg_version": "21.6-1.fc21",
                    "id": 69493,
                    "submitter": "asamalik"
                }
            }
        ],
        "_links": {
            "self": {
              "href": "/api_2/projects/2482?show_builds=True&show_chroots=True"
            },
            "chroots": {
              "href": "/api_2/projects/2482/chroots"
            },
            "builds": {
              "href": "/api_2/builds?project_id=2482"
            }
        }
    }"""
    project_1_id = 2482
    project_1_owner = "jmiahman"
    project_1_name = "Synergy-Linux"

    project_list_1 = """
{"_links": {"self": {"href": "/api_2/projects?limit=2"}},
"projects": [{"project": {"group": "copr", "name": "copr", "disable_createrepo": false, "repos": [],
"description": "Lightweight buildsystem -", "contact": null, "owner": "msuchy",
"build_enable_net": false, "homepage": null, "id": 1,
"instructions": "See https://pagure.io/copr/copr for more details."},
"_links": {"self": {"href": "/api_2/projects/1"},
"chroots": {"href": "/api_2/projects/1/chroots"},
"build_tasks": {"href": "/api_2/build_tasks?project_id=1"},
"builds": {"href": "/api_2/builds?project_id=1"}}},
{"project": {"name": "abrt", "disable_createrepo": false, "repos": [],
"description": "Experimental ABRT ",
"contact": null, "owner": "jfilak",
"build_enable_net": true, "homepage": null, "id": 9,
"instructions": "git branches- libreport : rhel6_upstream_ureport - abrt : rhel6_auto_reporting"},
"_links": {"self": {"href": "/api_2/projects/9"}, "chroots": {"href": "/api_2/projects/9/chroots"},
"build_tasks": {"href": "/api_2/build_tasks?project_id=9"}, "builds": {"href": "/api_2/builds?project_id=9"}}}]}
    """

    def test_get_one(self, project_handle):
        response = self.make_response(self.project_1)
        self.nc.request.return_value = response
        project = project_handle.get_one(
            self.project_1_id,
            #    show_builds=True, show_chroots=True
        )

        assert project.name == self.project_1_name
        assert project.owner == self.project_1_owner

    def test_get_list(self, project_handle):
        response = self.make_response(self.project_list_1)
        self.nc.request.return_value = response
        plist = project_handle.get_list()

        projects = plist.projects
        assert len(projects) == 2
        assert set([p.name for p in projects]) == set(["copr", "abrt"])

    def test_get_list_pass_options(self, project_handle):
        response = self.make_response(self.project_list_1)
        self.nc.request.return_value = response

        query_params = {
            "search_query": "Foo bar",
            "owner": "John Smith",
            "name": "void",
            "offset": 12,
            "limit": 5
        }
        project_handle.get_list(**query_params)
        ca = self.nc.request.call_args

        expected = query_params.copy()
        expected["group"] = None

        assert ca[0][0] == self.root_url + "/api_2/projects"
        assert ca[1]["query_params"] == expected

    @pytest.fixture
    def one_project(self, project_handle):
        response = self.make_response(self.project_1)
        self.nc.request.return_value = response
        one = project_handle.get_one(self.project_1_id)
        self.nc.reset_mock()
        return one

    def test_get_self(self, one_project):
        new_p = one_project.get_self()
        assert new_p.name == one_project.name
        assert new_p.owner == one_project.owner

    def test_update(self, one_project):
        new_value = "foo bar"
        one_project.instructions = new_value
        assert self.nc.request.called is False
        one_project.update()
        assert self.nc.request.called
        ca = self.nc.request.call_args
        assert ca[1]["method"] == "put"
        assert json.loads(ca[1]["data"])["instructions"] == new_value

    def test_delete(self, one_project):
        response = self.make_response("", status=204)
        self.nc.request.return_value = response
        res = one_project.delete()
        assert res.is_successful()
        assert self.nc.request.called
        ca = self.nc.request.call_args

        assert ca[1]["method"] == "delete"
        assert ca[0][0] == self.root_url + "/api_2/projects/{0}".format(self.project_1_id)
