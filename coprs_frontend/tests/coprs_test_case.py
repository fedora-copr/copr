import base64
import os
import time
from functools import wraps

import pytest
import decorator

import coprs

from coprs import helpers
from coprs import models


class CoprsTestCase(object):

    def setup_method(self, method):
        self.tc = coprs.app.test_client()
        self.app = coprs.app
        self.app.testing = True
        self.db = coprs.db
        self.db.session = self.db.create_scoped_session()
        self.models = models
        self.helpers = helpers
        self.backend_passwd = coprs.app.config['BACKEND_PASSWORD']
        # create datadir if it doesn't exist
        datadir = os.path.commonprefix(
            [self.app.config['DATABASE'], self.app.config['OPENID_STORE']])
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
        return {'Authorization': 'Basic ' +
                base64.b64encode('doesntmatter:{0}'.format(self.backend_passwd))}

    @pytest.fixture
    def f_db(self):
        self.db.session.commit()

    @pytest.fixture
    def f_users(self):
        self.u1 = models.User(
            openid_name=u'http://user1.id.fedoraproject.org/',
            proven=False,
            admin=True,
            mail='user1@foo.bar')

        self.u2 = models.User(
            openid_name=u'http://user2.id.fedoraproject.org/',
            proven=False,
            mail='user2@spam.foo')

        self.u3 = models.User(
            openid_name=u'http://user3.id.fedoraproject.org/',
            proven=False,
            mail='baz@bar.bar')

        self.db.session.add_all([self.u1, self.u2, self.u3])

    @pytest.fixture
    def f_coprs(self):
        self.c1 = models.Copr(name=u'foocopr', owner=self.u1)
        self.c2 = models.Copr(name=u'foocopr', owner=self.u2)
        self.c3 = models.Copr(name=u'barcopr', owner=self.u2)

        self.db.session.add_all([self.c1, self.c2, self.c3])

    @pytest.fixture
    def f_mock_chroots(self):
        self.mc1 = models.MockChroot(
            os_release='fedora', os_version='18', arch='x86_64', is_active=True)
        self.mc2 = models.MockChroot(
            os_release='fedora', os_version='17', arch='x86_64', is_active=True)
        self.mc3 = models.MockChroot(
            os_release='fedora', os_version='17', arch='i386', is_active=True)
        self.mc4 = models.MockChroot(
            os_release='fedora', os_version='rawhide', arch='i386', is_active=True)

        # only bind to coprs if the test has used the f_coprs fixture
        if hasattr(self, 'c1'):
            cc1 = models.CoprChroot()
            cc1.mock_chroot = self.mc1
            # c1 foocopr with fedora-18-x86_64
            self.c1.copr_chroots.append(cc1)

            cc2 = models.CoprChroot()
            cc2.mock_chroot = self.mc2
            cc3 = models.CoprChroot()
            cc3.mock_chroot = self.mc3
            # c2 foocopr with fedora-17-i386 fedora-17-x86_64
            self.c2.copr_chroots.append(cc2)
            self.c2.copr_chroots.append(cc3)

            cc4 = models.CoprChroot()
            cc4.mock_chroot = self.mc4
            # c3 barcopr with fedora-rawhide-i386
            self.c3.copr_chroots.append(cc4)
            self.db.session.add_all([cc1, cc2, cc3, cc4])

        self.db.session.add_all([self.mc1, self.mc2, self.mc3, self.mc4])

    @pytest.fixture
    def f_builds(self):
        self.b1 = models.Build(
            copr=self.c1, user=self.u1, submitted_on=50, started_on=139086644000)
        self.b2 = models.Build(
            copr=self.c1, user=self.u2, submitted_on=10, ended_on=139086644000)
        self.b3 = models.Build(
            copr=self.c2, user=self.u2, submitted_on=10)
        self.b4 = models.Build(
            copr=self.c2, user=self.u2, submitted_on=100)

        for build in [self.b1, self.b2, self.b3, self.b4]:
            self.db.session.add(build)

            for chroot in build.copr.active_chroots:
                buildchroot = models.BuildChroot(
                    build=build,
                    mock_chroot=chroot)

                self.db.session.add(buildchroot)

        self.db.session.add_all([self.b1, self.b2, self.b3, self.b4])

    @pytest.fixture
    def f_copr_permissions(self):
        self.cp1 = models.CoprPermission(
            copr=self.c2,
            user=self.u1,
            copr_builder=helpers.PermissionEnum('approved'),
            copr_admin=helpers.PermissionEnum('nothing'))

        self.cp2 = models.CoprPermission(
            copr=self.c3,
            user=self.u3,
            copr_builder=helpers.PermissionEnum('nothing'),
            copr_admin=helpers.PermissionEnum('nothing'))

        self.cp3 = models.CoprPermission(
            copr=self.c3,
            user=self.u1,
            copr_builder=helpers.PermissionEnum('request'),
            copr_admin=helpers.PermissionEnum('approved'))

        self.db.session.add_all([self.cp1, self.cp2, self.cp3])

    @pytest.fixture
    def f_actions(self):
        # if using actions, we need to flush coprs into db, so that we can get
        # their ids
        self.f_db()
        self.a1 = models.Action(action_type=helpers.ActionTypeEnum('rename'),
                                object_type='copr',
                                object_id=self.c1.id,
                                old_value='{0}/{1}'.format(
                                    self.c1.owner.name, self.c1.name),
                                new_value='{0}/new_name'.format(
                                    self.c1.owner.name),
                                created_on=int(time.time()))
        self.a2 = models.Action(action_type=helpers.ActionTypeEnum('rename'),
                                object_type='copr',
                                object_id=self.c2.id,
                                old_value='{0}/{1}'.format(
                                    self.c2.owner.name, self.c2.name),
                                new_value='{0}/new_name2'.format(
                                    self.c2.owner.name),
                                created_on=int(time.time()))
        self.a3 = models.Action(action_type=helpers.ActionTypeEnum('delete'),
                                object_type='copr',
                                object_id=100,
                                old_value='asd/qwe',
                                new_value=None,
                                result=helpers.BackendResultEnum('success'),
                                created_on=int(time.time()))
        self.db.session.add_all([self.a1, self.a2, self.a3])


class TransactionDecorator(object):

    """
    This is decorator as a class.

    Its purpose is to replace repetative lines of 'with' statements
    in test's functions. Everytime you find your self writing test function
    which uses following 'with's construct:

    with self.tc as test_client:
        with c.session_transaction() as session:
            session['openid'] = self.u.openid_name

    where 'u' stands for any user from 'f_users' fixture, use this to decorate
    your test function:

    @TransactionDecorator('u')
    def test_function_without_with_statements(self, f_users):
        # write code as you were in with 'self.tc as test_client' indent
        # you can also access object 'test_client' through 'self.test_client'

    where decorator parameter ''u'' stands for string representation of any
    user from 'f_users' fixture from which you wish to store 'openid_name'.
    Please note that you **must** include 'f_users' fixture in decorated
    function parameters.

    """

    def __init__(self, user):
        self.user = user

    def __call__(self, fn):
        @wraps(fn)
        def wrapper(fn, fn_self, *args):
            with fn_self.tc as fn_self.test_client:
                with fn_self.test_client.session_transaction() as session:
                    session['openid'] = getattr(fn_self, self.user).openid_name
                return fn(fn_self, *args)
        return decorator.decorator(wrapper, fn)
