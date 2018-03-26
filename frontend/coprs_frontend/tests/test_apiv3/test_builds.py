import json
from tests.coprs_test_case import CoprsTestCase


class TestBuilds(CoprsTestCase):
    #def test_get_build(self):
    def test_build_get_one(self, f_users, f_coprs, f_builds, f_db,
                           f_users_api, f_mock_chroots):

        build_id_list = [b.id for b in self.basic_builds]
        self.db.session.commit()
        b_id = build_id_list[0]

        href = "/api_3/build/{}".format(b_id)
        r = self.tc.get(href)
        assert r.status_code == 200
        obj = json.loads(r.data.decode("utf-8"))
        assert obj["build"]["id"] == b_id
        assert obj["_links"]["self"]["href"] == href
