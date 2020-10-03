"""
Library that simplifies interacting with Frontend routes.
"""

from bs4 import BeautifulSoup


def parse_web_form_error(html_text):
    """ return the list of form errors from failed form page """
    soup = BeautifulSoup(html_text, "html.parser")
    alerts = soup.findAll('div', class_='alert alert-danger')
    assert len(alerts) == 1
    div = alerts[0]
    return [li.text for li in div.find_all("li")]


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

    def new_project(self, name, chroots, bootstrap=None):
        """ Request Copr project creation.  Return the resonse. """
        raise NotImplementedError

    def edit_chroot(self, project, chroot, bootstrap=None,
                    bootstrap_image=None, owner=None):
        """ Modify CoprChroot """
        raise NotImplementedError

    def create_distgit_package(self, project, pkgname):
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

    def new_project(self, name, chroots, bootstrap=None):
        data = {"name": name}
        for ch in chroots:
            data[ch] = 'y'
        if bootstrap is not None:
            data["bootstrap"] = bootstrap
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
                    bootstrap_image=None, owner=None):
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

        resp = self.client.post(route, data=data)
        if self.success_expected:
            assert resp.status_code == 302
        return resp

    def create_distgit_package(self, project, pkgname):
        data = {
            "package_name": pkgname,
        }
        route = "/coprs/{user}/{project}/package/new/distgit".format(
            user=self.transaction_username,
            project=project,
        )
        resp = self.client.post(route, data=data)
        assert resp.status_code == 302
        return resp

    @staticmethod
    def _form_data_from_build_options(build_options):
        form_data = {}
        chroots = build_options.get("chroots")
        if chroots:
            for ch in chroots:
                form_data[ch] = 'y'

        for attr in ["bootstrap"]:
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

class API3Requests(_RequestsInterface):
    """
    Mimic python-copr API requests

    To successfully use this, the testing method needs to
    - use the TransactionDecorator()
    - use f_users_api fixture
    """

    def post(self, url, content):
        """ Post API3 form under "user" """
        return self.test_class_object.post_api3_with_auth(
            url, content, self.test_class_object.transaction_user)

    def get(self, url, content):
        """ Get API3 url with authenticated user """
        return self.test_class_object.get_api3_with_auth(
            url, content, self.test_class_object.transaction_user)

    def new_project(self, name, chroots, bootstrap=None):
        route = "/api_3/project/add/{}".format(self.transaction_username)
        data = {
            "name": name,
            "chroots": chroots,
        }
        if bootstrap is not None:
            data["bootstrap"] = bootstrap
        resp = self.post(route, data)
        return resp

    def edit_chroot(self, project, chroot, bootstrap=None,
                    bootstrap_image=None, owner=None):
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
        resp = self.post(route, data)
        return resp

    @staticmethod
    def _form_data_from_build_options(build_options):
        form_data = {}
        for arg in ["chroots", "bootstrap"]:
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

    def create_distgit_package(self, project, pkgname):
        route = "/api_3/package/add/{}/{}/{}/distgit".format(
            self.transaction_username, project, pkgname)
        resp = self.post(route, {"package_name": pkgname})
        return resp
