"""
Library that simplifies interacting with Frontend routes.
"""

import os
import json

from bs4 import BeautifulSoup
from werkzeug.datastructures import FileStorage

from coprs import models


# pylint: disable=consider-using-with


def parse_web_form_error(html_text, variant="a"):
    """ return the list of form errors from failed form page """
    soup = BeautifulSoup(html_text, "html.parser")

    if variant == "a":
        classes = "alert alert-danger"
    elif variant == "b":
        classes = "alert alert-danger alert-dismissable"

    alerts = soup.findAll('div', class_=classes)
    assert len(alerts) == 1
    div = alerts[0]
    if variant == "a":
        return [li.text for li in div.find_all("li")]
    return div.text.strip()


class _RequestsInterface:
    success_expected = True

    def __init__(self, test_class_object):
        self.test_class_object = test_class_object

    @property
    def client(self):
        """ Initialized flask http client """
        return self.test_class_object.test_client

    @property
    def transaction_username(self):
        """
        The name of the user we work with;  this only works if
        TransactionDecorator() is used
        """
        return self.test_class_object.transaction_username

    def new_project(self, name, chroots, **kwargs):
        """ Request Copr project creation.  Return the resonse. """
        raise NotImplementedError

    def edit_chroot(self, project, chroot, bootstrap=None,
                    bootstrap_image=None, owner=None, isolation=None,
                    additional_packages=None, reset_fields=None,
                    comps_filename=None):
        """ Modify CoprChroot """
        raise NotImplementedError

    def create_distgit_package(self, project, pkgname, options=None,
                               expected_status_code=None):
        """ Modify CoprChroot """
        raise NotImplementedError

    def submit_url_build(self, project, urls=None, build_options=None):
        """ Submit build using a Source RPM or SPEC URL """
        if urls is None:
            urls = "https://example.com/some.src.rpm"
        return self._submit_url_build(project, urls, build_options)

    def _submit_url_build(self, project, urls, build_options):
        raise NotImplementedError


class WebUIRequests(_RequestsInterface):
    """ Mimic Web UI request behavior """

    def new_project(self, name, chroots, **kwargs):
        data = {
            "name": name,
            "chroots": chroots,
        }

        for config in ['bootstrap', 'isolation', 'contact', 'homepage',
                       'appstream', 'follow_fedora_branching']:
            if not config in kwargs:
                continue
            data[config] = kwargs[config]

        resp = self.client.post(
            "/coprs/{0}/new/".format(self.transaction_username),
            data=data,
            follow_redirects=False,
        )
        # Errors are shown on the same page (HTTP 200), while successful
        # form submit is redirected (HTTP 302).
        assert resp.status_code == 302 if self.success_expected else 200
        return resp

    def edit_chroot(self, project, chroot, bootstrap=None,
                    bootstrap_image=None, owner=None, isolation=None,
                    additional_packages=None, reset_fields=None,
                    comps_filename=None):
        """ Change CoprChroot using the web-UI """
        route = "/coprs/{user}/{project}/update_chroot/{chroot}/".format(
            user=owner or self.transaction_username,
            project=project,
            chroot=chroot,
        )

        # this is hack, submit needs to have a value, check
        # the chroot_update() route for more info
        data = {"submit": "update"}

        if bootstrap is not None:
            data["bootstrap"] = bootstrap
        if bootstrap_image is not None:
            data["bootstrap_image"] = bootstrap_image
        if isolation is not None:
            data["isolation"] = isolation

        if comps_filename:
            data["comps"] = FileStorage(
                stream=open(comps_filename, "rb"),
                filename=os.path.basename(comps_filename),
                content_type="application/text",
            )

        resp = self.client.post(route, data=data,
                                content_type="multipart/form-data")
        if self.success_expected:
            assert resp.status_code == 302
        return resp

    def create_distgit_package(self, project, pkgname, options=None,
                               expected_status_code=None):
        if options:
            raise NotImplementedError
        data = {
            "package_name": pkgname,
        }
        route = "/coprs/{user}/{project}/package/new/distgit".format(
            user=self.transaction_username,
            project=project,
        )
        resp = self.client.post(route, data=data)
        assert resp.status_code == (expected_status_code or 302)
        return resp

    def cancel_build(self, project, build_id):
        route = "/coprs/{user}/{project}/cancel_build/{build_id}/".format(
            user=self.transaction_username,
            project=project,
            build_id=build_id,
        )
        resp = self.client.post(route, data={})
        assert resp.status_code == 302
        return resp

    @staticmethod
    def _form_data_from_build_options(build_options):
        if build_options is None:
            build_options = {}

        form_data = {"chroots": build_options.get("chroots")}
        for attr in ["bootstrap", "with_build_id", "after_build_id", "isolation"]:
            value = build_options.get(attr)
            if value is None:
                continue
            form_data[attr] = value

        return form_data

    def _submit_url_build(self, project, urls, build_options):
        """ Submit build by Web-UI from a src.rpm link """
        form_data = self._form_data_from_build_options(build_options)
        form_data["pkgs"] = urls
        route = "/coprs/{user}/{project}/new_build/".format(
            user=self.transaction_username,
            project=project,
        )
        resp = self.client.post(route, data=form_data)
        if resp.status_code != 302:
            print(parse_web_form_error(resp.data))
        assert resp.status_code == 302
        return resp

    def rebuild_all_packages(self, project_id, package_names=None):
        """ There's a button "rebuild-all" in web-UI, hit that button """
        copr = models.Copr.query.get(project_id)
        if not package_names:
            packages = copr.packages
            package_names = [p.name for p in packages]

        chroots = [mch.name for mch in copr.mock_chroots]
        route = "/coprs/{}/packages/rebuild-all/".format(copr.full_name)
        form_data = {
            "packages": package_names,
        }
        for ch in chroots:
            form_data[ch] = 'y'
        resp = self.client.post(route, data=form_data)
        return resp


class API3Requests(_RequestsInterface):
    """
    Mimic python-copr API requests

    To successfully use this, the testing method needs to
    - use the TransactionDecorator()
    - use f_users_api fixture
    """

    def post(self, url, content):
        """ Post API3 form under "user" """

        method = self.test_class_object.post_api3_with_auth
        for key in content:
            if isinstance(content[key], FileStorage):
                method = self.test_class_object.post_api3_with_auth_multipart
                break
        return method(
            url, content, self.test_class_object.transaction_user)

    def get(self, url, content):
        """ Get API3 url with authenticated user """
        return self.test_class_object.get_api3_with_auth(
            url, content, self.test_class_object.transaction_user)

    def new_project(self, name, chroots, **kwargs):
        route = "/api_3/project/add/{}".format(self.transaction_username)
        data = {
            "name": name,
            "chroots": chroots,
        }

        for config in ['bootstrap', 'isolation', 'contact', 'homepage', 'appstream']:
            if not config in kwargs:
                continue
            data[config] = kwargs[config]

        resp = self.post(route, data)
        assert resp.status_code == 200 if self.success_expected else 400
        return resp

    def modify_project(self, projectname, ownername=None, chroots=None,
                       **kwargs):
        """ Mimic "copr modify" """
        if ownername is None:
            ownername = self.transaction_username

        route = "/api_3/project/edit/{}/{}".format(ownername, projectname)

        data = {}
        if chroots:
            data["chroots"] = chroots

        for arg in kwargs:
            data[arg] = kwargs[arg]

        resp = self.post(route, data)
        assert resp.status_code == 200 if self.success_expected else 400
        return resp

    def edit_chroot(self, project, chroot, bootstrap=None,
                    bootstrap_image=None, owner=None, isolation=None,
                    additional_packages=None, reset_fields=None,
                    comps_filename=None):
        route = "/api_3/project-chroot/edit/{owner}/{project}/{chroot}".format(
            owner=owner or self.transaction_username,
            project=project,
            chroot=chroot,
        )
        data = {}
        if bootstrap is not None:
            data["bootstrap"] = bootstrap
        if bootstrap_image is not None:
            data["bootstrap_image"] = bootstrap_image
        if isolation is not None:
            data["isolation"] = isolation
        if additional_packages is not None:
            data["additional_packages"] = additional_packages
        if reset_fields is not None:
            data["reset_fields"] = reset_fields

        if comps_filename:
            data["upload_comps"] = FileStorage(
                stream=open(comps_filename, "rb"),
                filename=os.path.basename(comps_filename),
                content_type="application/text",
            )

        resp = self.post(route, data)
        return resp

    @staticmethod
    def _form_data_from_build_options(build_options):
        if not build_options:
            build_options = {}
        form_data = {}
        for arg in ["chroots", "bootstrap", "with_build_id", "after_build_id", "isolation"]:
            if arg not in build_options:
                continue
            if build_options[arg] is None:
                continue
            form_data[arg] = build_options[arg]
        return form_data

    def _submit_url_build(self, project, urls, build_options):
        route = "/api_3/build/create/url"
        data = {
            "ownername": self.transaction_username,
            "projectname": project,
            "pkgs": urls,
        }
        data.update(self._form_data_from_build_options(build_options))
        resp = self.post(route, data)
        return resp

    def submit_uploaded_build(self, project, source_rpm, build_options=None):
        """
        Submit a build via source RPM
        """
        route = "/api_3/build/create/upload"
        data = {
            "ownername": self.transaction_username,
            "projectname": project,
            "pkgs": FileStorage(
                stream=open(source_rpm, "rb"),
                filename=os.path.basename(source_rpm),
                content_type="application/rpm",
            )
        }
        data.update(self._form_data_from_build_options(build_options))
        return self.post(route, data)

    def create_distgit_package(self, project, pkgname, options=None,
                               expected_status_code=None):
        route = "/api_3/package/add/{}/{}/{}/distgit".format(
            self.transaction_username, project, pkgname)
        data = {"package_name": pkgname}
        if options is not None:
            data.update(options)
        resp = self.post(route, data)
        return resp

    def rebuild_package(self, project_dirname, pkgname, build_options=None,
                        project_ownername=None):
        """ Rebuild one package in a given project using API """
        project_name = project_dirname.split(":")[0]
        route = "/api_3/package/build"
        rebuild_data = {
            "ownername": project_ownername or self.transaction_username,
            "projectname": project_name,
            "package_name": pkgname,
            "project_dirname": project_dirname,
        }
        rebuild_data.update(self._form_data_from_build_options(build_options))
        return self.post(route, rebuild_data)


class BackendRequests:
    """ Requests on /backend/ namespace """
    def __init__(self, test_class_object):
        self.test_class_object = test_class_object

    @property
    def client(self):
        """ Initialized flask http client """
        return self.test_class_object.test_client

    def update(self, data):
        """ Post to the "/backend/update/" using a dict """
        return self.client.post(
            "/backend/update/",
            content_type="application/json",
            headers=self.test_class_object.auth_header,
            data=json.dumps(data),
        )

    def importing_queue(self):
        """ return the dict with importing tasks """
        resp = self.client.get(
            "/backend/importing/",
            content_type="application/json",
            headers=self.test_class_object.auth_header,
        )
        assert resp.status_code == 200
        return json.loads(resp.data)

    def fail_source_build(self, build_id):
        """ Mimic backend marking source build as failed """
        form_data = {
            "builds": [{
                "id": int(build_id),
                "task_id": str(build_id),
                "srpm_url": "http://foo",
                "status": 0,
            }],
        }
        assert self.update(form_data).status_code == 200


    def finish_build(self, build_id, package_name=None):
        """
        Given the build_id, finish the build with succeeded state
        """
        build = models.Build.query.get(build_id)
        if not package_name:
            package_name = build.package.name

        # finish srpm
        assert self.update({
            "builds": [{
                "id": build_id,
                "task_id": str(build_id),
                "srpm_url": "http://foo",
                "status": 1,
                "pkg_name": package_name,
                "pkg_version": 1
            }],
        }).status_code == 200

        # import srpm to appropriate branches
        build = models.Build.query.get(build_id)
        branch_commits = {}
        for bch in build.build_chroots:
            branch_commits[bch.mock_chroot.distgit_branch.name] = "4dc328232"
        assert self.client.post(
            "/backend/import-completed/",
            content_type="application/json",
            headers=self.test_class_object.auth_header,
            data=json.dumps({
               "build_id": build_id,
               "branch_commits": branch_commits,
               "reponame": "some/repo"
        }))

        # finish rpms
        update_requests = []
        for build_chroot in models.BuildChroot.query.filter_by(build_id=build_id).all():
            update_requests.append({
                "builds": [{
                    "id": build_id,
                    "build_id": build_id,
                    "task_id": "{}-{}".format(build_id, build_chroot.mock_chroot.name),
                    "chroot": build_chroot.mock_chroot.name,
                    "arch": build_chroot.mock_chroot.arch,
                    "status": 1,
                    "package_name": package_name,
                    "result_dir": "xyz",
                    "package_version": 1
                }],
            })

        for request in update_requests:
            assert self.update(request).status_code == 200
