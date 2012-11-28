import json

import flask

from tests.coprs_test_case import CoprsTestCase

class TestWaitingBuilds(CoprsTestCase):
    def test_no_waiting_builds(self):
        assert '"builds": []' in self.tc.get('/backend/waiting_builds/').data

    def test_waiting_build_only_lists_not_started_or_ended(self, f_users, f_coprs, f_builds):
        r = self.tc.get('/backend/waiting_builds/')
        assert len(json.loads(r.data)['builds']) == 2

class TestUpdateBuilds(CoprsTestCase):
    def test_updating_requires_password(self, f_users, f_coprs, f_builds):
        r = self.tc.post('/backend/update_builds/',
                         content_type = 'application/json',
                         data = '')
        assert 'You have to provide the correct password' in r.data

    def test_update_build_started(self, f_users, f_coprs, f_builds):
        data = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "results": "http://server/results/$ownername/$coprname/",
     "started_on": 1234
   }
  ]
}
        """
        r = self.tc.post('/backend/update_builds/',
                         content_type='application/json',
                         headers = self.auth_header,
                         data = data)
        assert r.data == '{"updated_builds": 1}'
