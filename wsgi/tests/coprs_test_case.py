import os
os.environ['COPRS_ENVIRON_UNITTEST'] = '1'

import pytest

import coprs

from coprs import models

class CoprsTestCase(object):
    def setup_method(self, method):
        self.tc = coprs.app.test_client()
        self.app = coprs.app
        self.app.testing = True
        self.db = coprs.db
        self.models = models
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
    def f_users(self):
        self.u1 = models.User(openid_name = 'http://user1.id.fedoraproject.org/', proven = False)
        self.u2 = models.User(openid_name = 'http://user2.id.fedoraproject.org/', proven = False)
        self.u3 = models.User(openid_name = 'http://user3.id.fedoraproject.org/', proven = False)

        self.db.session.add_all([self.u1, self.u2, self.u3])
        self.db.session.commit()

    @pytest.fixture
    def f_coprs(self):
        self.c1 = models.Copr(name = 'foocopr', chroots = 'fedora-18-x86_64', owner = self.u1)
        self.c2 = models.Copr(name = 'foocopr', chroots = 'fedora-17-x86_64 fedora-17-i386', owner = self.u2)
        self.c3 = models.Copr(name = 'barcopr', chroots = 'fedora-rawhide-i386', owner = self.u2)

        self.db.session.add_all([self.c1, self.c2, self.c3])
        self.db.session.commit()

    @pytest.fixture
    def f_builds(self):
        self.b1 = models.Build(copr = self.c1, user = self.u1, chroots = self.c1.chroots, submitted_on = 50)
        self.b2 = models.Build(copr = self.c1, user = self.u2, chroots = 'fedora-17-x86_64', submitted_on = 10)
        self.b3 = models.Build(copr = self.c2, user = self.u2, chroots = self.c2.chroots, submitted_on = 10)
        self.b4 = models.Build(copr = self.c2, user = self.u2, chroots = self.c2.chroots, submitted_on = 100)

        self.db.session.add_all([self.b1, self.b2, self.b3, self.b4])
        self.db.session.commit()

    @pytest.fixture
    def f_copr_permissions(self):
        self.cp1 = models.CoprPermission(copr = self.c2, user = self.u1, approved = True)
        self.cp2 = models.CoprPermission(copr = self.c3, user = self.u3, approved = False)
        self.cp3 = models.CoprPermission(copr = self.c3, user = self.u1, approved = False)

        self.db.session.add_all([self.cp1, self.cp2, self.cp3])
        self.db.session.commit()
