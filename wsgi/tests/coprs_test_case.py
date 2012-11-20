import os
os.environ['COPRS_ENVIRON_UNITTEST'] = '1'

import pytest

import coprs

from coprs import models

class CoprsTestCase(object):
    def setup_method(self, method):
        self.tc = coprs.app.test_client()
        self.app = coprs.app
        self.db = coprs.db

        # create datadir if it doesn't exist
        datadir = os.path.commonprefix([self.app.config['DATABASE'], self.app.config['OPENID_STORE']])
        if not os.path.exists(datadir):
            os.makedirs(datadir)

        coprs.db.create_all()

    def teardown_method(self, method):
        # delete just data, not the tables
        for tbl in reversed(self.db.metadata.sorted_tables):
            self.db.engine.execute(tbl.delete())

    @pytest.fixture
    def f_data1(self):
        u = models.User(openid_name = 'user1', proven = False)
        c = models.Copr(name = 'foocopr', chroots = 'fedora-18-x86_64', owner = u)

        self.db.session.add_all([u, c])
        self.db.session.commit()
