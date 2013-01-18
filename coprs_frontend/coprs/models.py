import datetime

from coprs import constants
from coprs import db
from coprs import helpers

class Serializer(object):
    def to_dict(self, options = {}):
        """Usage:
        SQLAlchObject.to_dict() => returns a flat dict of the object
        SQLAlchObject.to_dict({'foo': {}}) => returns a dict of the object and will include a
            flat dict of object foo inside of that
        SQLAlchObject.to_dict({'foo': {'bar': {}}, 'spam': {}}) => returns a dict of the object,
            which will include dict of foo (which will include dict of bar) and dict of spam

        Options can also contain two special values: __columns_only__ and __columns_except__
        If present, the first makes only specified fiels appear, the second removes specified fields.
        Both of these fields must be either strings (only works for one field) or lists (for one and more fields).
        SQLAlchObject.to_dict({'foo': {'__columns_except__': ['id']}, '__columns_only__': 'name'}) =>
        The SQLAlchObject will only put its 'name' into the resulting dict, while 'foo' all of its fields except 'id'.

        Options can also specify whether to include foo_id when displaying related foo object
        (__included_ids__, defaults to True). This doesn't apply when __columns_only__ is specified.
        """
        result = {}
        columns = self.serializable_attributes

        if options.has_key('__columns_only__'):
            columns = options['__columns_only__']
        else:
            columns = set(columns)
            if options.has_key('__columns_except__'):
                columns_except = options['__columns_except__'] if isinstance(options['__columns_except__'], list) else [options['__columns_except__']]
                columns -= set(columns_except)
            if options.has_key('__included_ids__') and options['__included_ids__'] == False:
                related_objs_ids = [r + '_id' for r, o in options.items() if not r.startswith('__')]
                columns -= set(related_objs_ids)

            columns = list(columns)

        for column in columns:
            result[column] = getattr(self, column)

        for related, values in options.items():
            if hasattr(self, related):
                result[related] = getattr(self, related).to_dict(values)
        return result

    @property
    def serializable_attributes(self):
        return map(lambda x: x.name, self.__table__.columns)

class User(db.Model, Serializer):
    id = db.Column(db.Integer, primary_key = True)
    openid_name = db.Column(db.String(100), nullable = False)
    mail = db.Column(db.String(150), nullable = False)
    proven = db.Column(db.Boolean, default = False)
    admin = db.Column(db.Boolean, default = False)
    api_token = db.Column(db.String(40), nullable = False, default = 'abc')
    api_token_expiration = db.Column(db.Date, nullable = False, default = datetime.date(2000, 1, 1))

    @property
    def name(self):
        return self.openid_name.replace('.id.fedoraproject.org/', '').replace('http://', '')

    def permissions_for_copr(self, copr): # simple caching of permissions for given copr
        # we can't put this into class declaration because the class may be shared by multiple threads
        if not hasattr(self, '_permissions_for_copr'):
            self._permissions_for_copr = {}
        if not copr.name in self._permissions_for_copr:
            self._permissions_for_copr[copr.name] = CoprPermission.query.filter_by(user = self).filter_by(copr = copr).first()
        return self._permissions_for_copr[copr.name]

    def can_build_in(self, copr):
        can_build = False
        if copr.owner == self:
            can_build = True
        if self.permissions_for_copr(copr) and self.permissions_for_copr(copr).copr_builder == helpers.PermissionEnum.num('approved'):
            can_build = True

        return can_build

    def can_edit(self, copr):
        can_edit = False
        if copr.owner == self:
            can_edit = True
        if self.permissions_for_copr(copr) and self.permissions_for_copr(copr).copr_admin == helpers.PermissionEnum.num('approved'):
            can_edit = True

        return can_edit

    @classmethod
    def openidize_name(cls, name):
        return 'http://{0}.id.fedoraproject.org/'.format(name)

    @property
    def serializable_attributes(self):
        # enumerate here to prevent exposing credentials
        return ['id', 'name']

    @property
    def coprs_count(self):
        return Copr.query.filter_by(owner=self).count()


class Copr(db.Model, Serializer):
    id = db.Column(db.Integer, primary_key = True)
    name = db.Column(db.String(100), nullable = False)
    repos = db.Column(db.Text)
    created_on = db.Column(db.Integer)
    # duplicate information, but speeds up a lot and makes queries simpler
    build_count = db.Column(db.Integer, default = 0)

    # relations
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    owner = db.relationship('User', backref = db.backref('coprs'))

    @property
    def repos_list(self):
        return self.repos.split(' ')

    @property
    def mock_chroots(self):
        if not hasattr(self, '_mock_chroots'):
            self._mock_chroots = MockChroot.query.join(CoprChroot).\
                                                  filter(CoprChroot.copr_id==self.id).\
                                                  filter(MockChroot.is_active==True).all()
            self._mock_chroots.sort(cmp=lambda x,y: cmp(x.chroot_name, y.chroot_name))

        return self._mock_chroots

    __mapper_args__ = {'order_by': id.desc()}

class CoprPermission(db.Model, Serializer):
    # 0 = nothing, 1 = asked for, 2 = approved
    # not using enum, as that translates to varchar on some DBs
    copr_builder = db.Column(db.SmallInteger, default = 0)
    copr_admin = db.Column(db.SmallInteger, default = 0)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key = True)
    user = db.relationship('User', backref = db.backref('copr_permissions'))
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'), primary_key = True)
    copr = db.relationship('Copr', backref = db.backref('copr_permissions'))

class Build(db.Model, Serializer):
    id = db.Column(db.Integer, primary_key = True)
    pkgs = db.Column(db.Text)
    canceled = db.Column(db.Boolean, default = False)
    # These two are present for every build, as they might change in Copr
    # between submitting and starting build => we want to keep them as submitted
    chroots = db.Column(db.Text, nullable = False)
    repos = db.Column(db.Text)
    submitted_on = db.Column(db.Integer, nullable = False)
    started_on = db.Column(db.Integer)
    ended_on = db.Column(db.Integer)
    results = db.Column(db.Text)
    status = db.Column(db.Integer)
    memory_reqs = db.Column(db.Integer, default = constants.DEFAULT_BUILD_MEMORY)
    timeout = db.Column(db.Integer, default = constants.DEFAULT_BUILD_TIMEOUT)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref = db.backref('builds'))
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'))
    copr = db.relationship('Copr', backref = db.backref('builds'))

    @property
    def state(self):
        if self.status == 1:
            return 'succeeded'
        elif self.status == 0:
            return 'failed'
        if self.canceled:
            return 'canceled'
        if not self.ended_on and self.started_on:
            return 'running'
        return 'pending'

    @property
    def cancelable(self):
        return self.state == 'pending'

class MockChroot(db.Model, Serializer):
    id = db.Column(db.Integer, primary_key = True)
    os_release = db.Column(db.String(50), nullable = False) # fedora/epel/...
    os_version = db.Column(db.String(50), nullable = False) # 18/rawhide/...
    arch = db.Column(db.String(50), nullable = False) # x86_64/i686/...
    is_active = db.Column(db.Boolean, default = True)

    @property
    def chroot_name(self):
        return '{0}-{1}-{2}'.format(self.os_release, self.os_version, self.arch)

    @classmethod
    def get(cls, os_release, os_version, arch, active_only = False):
        return cls.query.filter(cls.os_release==os_release,
                                cls.os_version==os_version,
                                cls.arch==arch).first()

class CoprChroot(db.Model, Serializer):
    mock_chroot_id = db.Column(db.Integer, db.ForeignKey('mock_chroot.id'), primary_key = True)
    mock_chroot = db.relationship('MockChroot', backref = db.backref('copr_chroots'))
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'), primary_key = True)
    copr = db.relationship('Copr', backref = db.backref('copr_chroots'))
