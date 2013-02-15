import json

import flask

from coprs.signals import build_finished
from tests.coprs_test_case import CoprsTestCase

class TestWaitingBuilds(CoprsTestCase):
    def test_no_waiting_builds(self):
        assert '"builds": []' in self.tc.get('/backend/waiting_builds/').data

    def test_waiting_build_only_lists_not_started_or_ended(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.get('/backend/waiting_builds/')
        assert len(json.loads(r.data)['builds']) == 2

class TestUpdateBuilds(CoprsTestCase):
    data1="""
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "results": "http://server/results/foo/bar/",
     "started_on": 1234
   }
  ]
}"""

    data2 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "status": 1,
     "ended_on": 12345
   }
  ]
}"""
    
    data3 = """
{
  "builds":[
   {
     "id": 1,
     "copr_id": 2,
     "results": "http://server/results/foo/bar/",
     "started_on": 1234
   },
   {
     "id": 2,
     "copr_id": 1,
     "status": 0,
     "ended_on": 123456
   },
   {
     "id": 123321,
     "copr_id": 1,
     "status": 0,
     "ended_on": 123456
   },
   {
     "id": 1234321,
     "copr_id": 2,
     "results": "http://server/results/foo/bar/",
     "started_on": 1234
   }
  ]
}"""
    def test_updating_requires_password(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.post('/backend/update_builds/',
                         content_type = 'application/json',
                         data = '')
        assert 'You have to provide the correct password' in r.data

    def test_update_build_started(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.post('/backend/update_builds/',
                         content_type='application/json',
                         headers=self.auth_header,
                         data=self.data1)
        assert json.loads(r.data)["updated_builds_ids"] == [1]
        assert json.loads(r.data)["non_existing_builds_ids"] == []

        updated = self.models.Build.query.filter(self.models.Build.id==1).first()
        assert updated.results == 'http://server/results/foo/bar/'
        assert updated.started_on == 1234

    def test_update_build_ended(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.post('/backend/update_builds/',
                         content_type='application/json',
                         headers=self.auth_header,
                         data=self.data2)
        assert json.loads(r.data)["updated_builds_ids"] == [1]
        assert json.loads(r.data)["non_existing_builds_ids"] == []

        updated = self.models.Build.query.filter(self.models.Build.id==1).first()
        assert updated.status == 1
        assert updated.ended_on == 12345

    def test_update_more_existent_and_non_existent_builds(self, f_users, f_coprs, f_builds, f_db):
        r = self.tc.post('/backend/update_builds/',
                         content_type='application/json',
                         headers=self.auth_header,
                         data=self.data3)

        assert sorted(json.loads(r.data)["updated_builds_ids"]) == [1, 2]
        assert sorted(json.loads(r.data)["non_existing_builds_ids"]) == [123321, 1234321]

        started = self.models.Build.query.filter(self.models.Build.id==1).first()
        assert started.results == 'http://server/results/foo/bar/'
        assert started.started_on == 1234

        ended = self.models.Build.query.filter(self.models.Build.id==2).first()
        assert ended.status == 0
        assert ended.ended_on == 123456

    def test_build_ended_emmits_signal(self, f_users, f_coprs, f_builds, f_db):
        # TODO: this should probably be mocked...
        signals_received = []
        def test_receiver(sender, **kwargs):
            signals_received.append(kwargs['build'])
        build_finished.connect(test_receiver)
        r = self.tc.post('/backend/update_builds/',
                         content_type='application/json',
                         headers=self.auth_header,
                         data=self.data3)
        assert len(signals_received) == 1
        self.db.session.add(self.b2)
        assert signals_received[0].id == 2
