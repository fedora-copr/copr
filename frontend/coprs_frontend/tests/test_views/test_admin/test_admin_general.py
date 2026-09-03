# pylint: disable=unused-argument
from tests.coprs_test_case import CoprsTestCase


class TestAdminLogin(CoprsTestCase):
    # TODO: test on something better then page title - maybe see rendered
    # templates?
    text_to_check = "Coprs - Admin"

    def test_nonadmin_cant_login(self, f_users, f_db):
        with self.tc as c:
            with c.session_transaction() as s:
                s["oidc"] = self.u2.username

        r = c.get("/admin/", follow_redirects=True)
        assert self.text_to_check not in r.data.decode("utf-8")

    def test_admin_can_login(self, f_users, f_db):
        with self.tc as c:
            with c.session_transaction() as s:
                s["oidc"] = self.u1.username

        r = c.get("/admin/", follow_redirects=True)
        assert self.text_to_check in r.data.decode("utf-8")


class TestAdminTags(CoprsTestCase):
    """
    Tests for the admin tag management routes
    """

    def _login_as_admin(self, c):
        """
        Log the test client in as the admin user.
        """
        with c.session_transaction() as s:
            s["oidc"] = self.u1.username

    def test_create_tag_marks_default(self, f_users, f_db):
        """
        Creating a tag via the admin route marks it as default immediately.
        """
        with self.tc as c:
            self._login_as_admin(c)
            c.post("/admin/tags/create/", data={"name": "cli"},
                   follow_redirects=True)

        tag = self.models.ProjectTag.query.filter_by(name="cli").first()
        assert tag is not None
        assert tag.is_default is True

    def test_rename_tag(self, f_users, f_db):
        """
        Renaming a tag updates its name in place.
        """
        tag = self.models.ProjectTag(name="cli", is_default=False, created_on=1)
        self.db.session.add(tag)
        self.db.session.commit()

        with self.tc as c:
            self._login_as_admin(c)
            c.post(f"/admin/tags/{tag.id}/rename/",
                   data={"name": "cli-tool"}, follow_redirects=True)

        self.db.session.expire(tag)
        assert tag.name == "cli-tool"

    def test_rename_whole_input_as_one_name(self, f_users, f_db):
        """
        Regression test: a comma in the rename input must not silently drop
        part of the name (it isn't the multi-tag Create field).
        """
        tag = self.models.ProjectTag(name="cli", is_default=False, created_on=1)
        self.db.session.add(tag)
        self.db.session.commit()

        with self.tc as c:
            self._login_as_admin(c)
            c.post(f"/admin/tags/{tag.id}/rename/",
                   data={"name": "hello, hi"}, follow_redirects=True)

        self.db.session.expire(tag)
        assert tag.name == "hello-hi"
