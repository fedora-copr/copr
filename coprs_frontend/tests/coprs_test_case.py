import base64
import os
import time

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
        self.db.session.commit()

    def teardown_method(self, method):
        # delete just data, not the tables
        for tbl in reversed(self.db.metadata.sorted_tables):
            self.db.engine.execute(tbl.delete())

    @property
    def auth_header(self):
        return {'Authorization': 'Basic ' + base64.b64encode('doesntmatter:{0}'.format(self.backend_passwd))}

    @pytest.fixture
    def f_db(self):
        self.db.session.commit()

    @pytest.fixture
    def f_users(self):
        self.u1 = models.User(openid_name = u'http://user1.id.fedoraproject.org/', proven = False, mail = 'user1@foo.bar')
        self.u2 = models.User(openid_name = u'http://user2.id.fedoraproject.org/', proven = False, mail = 'user2@spam.foo')
        self.u3 = models.User(openid_name = u'http://user3.id.fedoraproject.org/', proven = False, mail = 'baz@bar.bar')

        self.db.session.add_all([self.u1, self.u2, self.u3])

    @pytest.fixture
    def f_coprs(self):
        self.c1 = models.Copr(name = u'foocopr', owner = self.u1)
        self.c2 = models.Copr(name = u'foocopr', owner = self.u2)
        self.c3 = models.Copr(name = u'barcopr', owner = self.u2)

        self.db.session.add_all([self.c1, self.c2, self.c3])

    @pytest.fixture
    def f_mock_chroots(self):
        self.mc1 = models.MockChroot(os_release='fedora', os_version='18', arch='x86_64', is_active=True)
        self.mc2 = models.MockChroot(os_release='fedora', os_version='17', arch='x86_64', is_active=True)
        self.mc3 = models.MockChroot(os_release='fedora', os_version='17', arch='i386', is_active=True)
        self.mc4 = models.MockChroot(os_release='fedora', os_version='rawhide', arch='i386', is_active=True)

        # only bind to coprs if the test has used the f_coprs fixture
        if hasattr(self, 'c1'):
            cc1 = models.CoprChroot()
            cc1.mock_chroot = self.mc1
            self.c1.copr_chroots.append(cc1)

            cc2 = models.CoprChroot()
            cc2.mock_chroot = self.mc2
            cc3 = models.CoprChroot()
            cc3.mock_chroot = self.mc3
            self.c2.copr_chroots.append(cc2)
            self.c2.copr_chroots.append(cc3)

            cc4 = models.CoprChroot()
            cc4.mock_chroot = self.mc4
            self.c3.copr_chroots.append(cc4)
            self.db.session.add_all([cc1, cc2, cc3, cc4])

        self.db.session.add_all([self.mc1, self.mc2, self.mc3, self.mc4])

    @pytest.fixture
    def f_builds(self):
        self.b1 = models.Build(copr = self.c1, user = self.u1, chroots = 'fedora-18-x86_64', submitted_on = 50, started_on = 100)
        self.b2 = models.Build(copr = self.c1, user = self.u2, chroots = 'fedora-17-x86_64', submitted_on = 10, ended_on = 150)
        self.b3 = models.Build(copr = self.c2, user = self.u2, chroots = 'fedora-17-x86_64 fedora-17-i386', submitted_on = 10)
        self.b4 = models.Build(copr = self.c2, user = self.u2, chroots = 'fedora-17-x86_64 fedora-17-i386', submitted_on = 100)

        self.db.session.add_all([self.b1, self.b2, self.b3, self.b4])

    @pytest.fixture
    def f_copr_permissions(self):
        self.cp1 = models.CoprPermission(copr = self.c2, user = self.u1, copr_builder = helpers.PermissionEnum('approved'), copr_admin = helpers.PermissionEnum('nothing'))
        self.cp2 = models.CoprPermission(copr = self.c3, user = self.u3, copr_builder = helpers.PermissionEnum('nothing'), copr_admin = helpers.PermissionEnum('nothing'))
        self.cp3 = models.CoprPermission(copr = self.c3, user = self.u1, copr_builder = helpers.PermissionEnum('request'), copr_admin = helpers.PermissionEnum('approved'))

        self.db.session.add_all([self.cp1, self.cp2, self.cp3])

    @pytest.fixture
    def f_actions(self):
        self.a1 = models.Action(action_type=helpers.ActionTypeEnum('rename'),
                                object_type='copr',
                                object_id=self.c1.id,
                                old_value='{0}/{1}'.format(self.c1.owner.name, self.c1.name),
                                new_value='{0}/new_name'.format(self.c1.owner.name),
                                created_on=int(time.time()))
        self.a2 = models.Action(action_type=helpers.ActionTypeEnum('rename'),
                                object_type='copr',
                                object_id=self.c2.id,
                                old_value='{0}/{1}'.format(self.c2.owner.name, self.c2.name),
                                new_value='{0}/new_name2'.format(self.c2.owner.name),
                                created_on=int(time.time()))
        self.a3 = models.Action(action_type=helpers.ActionTypeEnum('delete'),
                                object_type='copr',
                                object_id=100,
                                old_value='asd/qwe',
                                new_value=None,
                                backend_result=helpers.BackendResultEnum('success'),
                                created_on=int(time.time()))
        self.db.session.add_all([self.a1, self.a2, self.a3])
