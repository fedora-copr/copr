import base64
import os
os.environ['COPRS_ENVIRON_UNITTEST'] = '1'

import pytest

import coprs

from coprs import helpers
from coprs import models

class CoprsTestCase(object):
    def setup_method(self, method):
        self.tc = coprs.app.test_client()
        self.app = coprs.app
        self.app.testing = True
        self.db = coprs.db
        self.models = models
        self.helpers = helpers
        self.backend_passwd = coprs.app.config['BACKEND_PASSWORD']
        # create datadir if it doesn't exist
        datadir = os.path.commonprefix([self.app.config['DATABASE'], self.app.config['OPENID_STORE']])
        if not os.path.exists(datadir):
            os.makedirs(datadir)

        coprs.db.create_all()

    def teardown_method(self, method):
        # delete just data, not the tables
        for tbl in reversed(self.db.metadata.sorted_tables):
            self.db.engine.execute(tbl.delete())

    @property
    def auth_header(self):
        return {'Authorization': 'Basic ' + base64.b64encode('doesntmatter:{0}'.format(self.backend_passwd))}

    @pytest.fixture
    def f_users(self):
        self.u1 = models.User(openid_name = 'http://user1.id.fedoraproject.org/', proven = False, mail = 'user1@foo.bar')
        self.u2 = models.User(openid_name = 'http://user2.id.fedoraproject.org/', proven = False, mail = 'user2@spam.foo')
        self.u3 = models.User(openid_name = 'http://user3.id.fedoraproject.org/', proven = False, mail = 'baz@bar.bar')

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
        self.b1 = models.Build(copr = self.c1, user = self.u1, chroots = self.c1.chroots, submitted_on = 50, started_on = 100)
        self.b2 = models.Build(copr = self.c1, user = self.u2, chroots = 'fedora-17-x86_64', submitted_on = 10, ended_on = 150)
        self.b3 = models.Build(copr = self.c2, user = self.u2, chroots = self.c2.chroots, submitted_on = 10)
        self.b4 = models.Build(copr = self.c2, user = self.u2, chroots = self.c2.chroots, submitted_on = 100)

        self.db.session.add_all([self.b1, self.b2, self.b3, self.b4])
        self.db.session.commit()

    @pytest.fixture
    def f_copr_permissions(self):
        self.cp1 = models.CoprPermission(copr = self.c2, user = self.u1, copr_builder = helpers.PermissionEnum.num('approved'), copr_admin = helpers.PermissionEnum.num('nothing'))
        self.cp2 = models.CoprPermission(copr = self.c3, user = self.u3, copr_builder = helpers.PermissionEnum.num('nothing'), copr_admin = helpers.PermissionEnum.num('nothing'))
        self.cp3 = models.CoprPermission(copr = self.c3, user = self.u1, copr_builder = helpers.PermissionEnum.num('request'), copr_admin = helpers.PermissionEnum.num('approved'))

        self.db.session.add_all([self.cp1, self.cp2, self.cp3])
        self.db.session.commit()
