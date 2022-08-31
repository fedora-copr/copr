import os
import pytest
from coprs import models
from tests.coprs_test_case import CoprsTestCase, TransactionDecorator


class TestComps(CoprsTestCase):
    @TransactionDecorator("u1")
    @pytest.mark.usefixtures("f_users", "f_coprs", "f_users_api",
                             "f_mock_chroots", "f_db")
    @pytest.mark.parametrize("request_type", ["api", "webui"])
    def test_edit_project_chroot_comps(self, request_type):
        client = self.api3 if request_type == "api" else self.web_ui
        self.db.session.add(self.c1)
        chroot = self.c1.copr_chroots[0]
        chroot_id = chroot.id

        workdir = os.path.join(os.path.dirname(__file__))
        comps_f = os.path.join(workdir, "data", "comps.xml")
        client.edit_chroot(
            self.c1.name, chroot.name,
            comps_filename=comps_f,
            bootstrap_image="image",
        )

        chroot = models.CoprChroot.query.get(chroot_id)
        data = "<some><xml></xml></some>\n"
        assert chroot.comps == data
        assert chroot.bootstrap_image == "image"

        result = self.tc.get("/coprs/user1/foocopr/chroot/{}/comps/".format(
            chroot.name,
        ))
        assert result.data.decode("utf-8") == data
