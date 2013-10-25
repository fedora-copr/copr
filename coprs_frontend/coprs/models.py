import datetime
import time

import sqlalchemy
from sqlalchemy.ext.associationproxy import association_proxy
from libravatar import libravatar_url

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
    """Represents user of the copr frontend"""
    id = db.Column(db.Integer, primary_key = True)
    # openid_name for fas, e.g. http://bkabrda.id.fedoraproject.org/
    openid_name = db.Column(db.String(100), nullable = False)
    # just mail :)
    mail = db.Column(db.String(150), nullable = False)
    # is this user proven? proven users can modify builder memory and timeout for single builds
    proven = db.Column(db.Boolean, default = False)
    # is this user admin of the system?
    admin = db.Column(db.Boolean, default = False)
    # stuff for the cli interface
    api_login = db.Column(db.String(40), nullable = False, default = 'abc')
    api_token = db.Column(db.String(40), nullable = False, default = 'abc')
    api_token_expiration = db.Column(db.Date, nullable = False, default = datetime.date(2000, 1, 1))

    @property
    def name(self):
        """Returns the short username of the user, e.g. bkabrda"""
        return self.openid_name.replace('.id.fedoraproject.org/', '').replace('http://', '')

    def permissions_for_copr(self, copr):
        """Get permissions of this user for the given copr.
        Caches the permission during one request, so use this if you access them multiple times
        """
        if not hasattr(self, '_permissions_for_copr'):
            self._permissions_for_copr = {}
        if not copr.name in self._permissions_for_copr:
            self._permissions_for_copr[copr.name] = CoprPermission.query.filter_by(user = self).filter_by(copr = copr).first()
        return self._permissions_for_copr[copr.name]

    def can_build_in(self, copr):
        """Determine if this user can build in the given copr."""
        can_build = False
        if copr.owner == self:
            can_build = True
        if self.permissions_for_copr(copr) and self.permissions_for_copr(copr).copr_builder == helpers.PermissionEnum('approved'):
            can_build = True

        return can_build

    def can_edit(self, copr):
        """Determine if this user can edit the given copr."""
        can_edit = False
        if copr.owner == self:
            can_edit = True
        if self.permissions_for_copr(copr) and self.permissions_for_copr(copr).copr_admin == helpers.PermissionEnum('approved'):
            can_edit = True

        return can_edit

    @classmethod
    def openidize_name(cls, name):
        """Creates proper openid_name from short name.

        >>> user.openid_name == User.openidize_name(user.name)
        True
        """
        return 'http://{0}.id.fedoraproject.org/'.format(name)

    @property
    def serializable_attributes(self):
        # enumerate here to prevent exposing credentials
        return ['id', 'name']

    @property
    def coprs_count(self):
        """Get number of coprs for this user."""
        return Copr.query.filter_by(owner=self).\
                          filter_by(deleted=False).\
                          count()

    @property
    def gravatar_url(self):
        """Return url to libravatar image."""
        try:
            return libravatar_url(email = self.mail)
        except IOError:
            return "" 


class Copr(db.Model, Serializer):
    """Represents a single copr (private repo with builds, mock chroots, etc.)."""
    id = db.Column(db.Integer, primary_key = True)
    # name of the copr, no fancy chars (checked by forms)
    name = db.Column(db.String(100), nullable = False)
    # string containing urls of additional repos (separated by space)
    # that this copr will pull dependencies from
    repos = db.Column(db.Text)
    # time of creation as returned by int(time.time())
    created_on = db.Column(db.Integer)
    # description and instructions given by copr owner
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    # duplicate information, but speeds up a lot and makes queries simpler
    build_count = db.Column(db.Integer, default = 0)
    deleted = db.Column(db.Boolean, default=False)

    # relations
    owner_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    owner = db.relationship('User', backref = db.backref('coprs'))
    mock_chroots = association_proxy('copr_chroots', 'mock_chroot')

    __mapper_args__ = {
        'order_by' : created_on.desc()
    }

    @property
    def repos_list(self):
        """Returns repos of this copr as a list of strings"""
        return self.repos.split()

    @property
    def description_or_not_filled(self):
        return self.description or 'Description not filled in by author.'

    @property
    def instructions_or_not_filled(self):
        return self.instructions or 'Instructions not filled in by author.'

    @property
    def active_mock_chroots(self):
        """Returns list of active mock_chroots of this copr"""
        return filter(lambda x: x.is_active, self.mock_chroots)

class CoprPermission(db.Model, Serializer):
    """Association class for Copr<->Permission relation"""
    ## see helpers.PermissionEnum for possible values of the fields below
    # can this user build in the copr?
    copr_builder = db.Column(db.SmallInteger, default = 0)
    # can this user serve as an admin? (-> edit and approve permissions)
    copr_admin = db.Column(db.SmallInteger, default = 0)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key = True)
    user = db.relationship('User', backref = db.backref('copr_permissions'))
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'), primary_key = True)
    copr = db.relationship('Copr', backref = db.backref('copr_permissions'))

class Build(db.Model, Serializer):
    """Representation of one build in one copr"""
    id = db.Column(db.Integer, primary_key = True)
    # list of space separated urls of packages to build
    pkgs = db.Column(db.Text)
    # was this build canceled by user?
    canceled = db.Column(db.Boolean, default = False)
    ## These two are present for every build, as they might change in Copr
    ## between submitting and starting build => we want to keep them as submitted
    # list of space separated mock chroot names
    chroots = db.Column(db.Text, nullable = False)
    # list of space separated additional repos
    repos = db.Column(db.Text)
    ## the three below represent time of important events for this build
    ## as returned by int(time.time())
    submitted_on = db.Column(db.Integer, nullable = False)
    started_on = db.Column(db.Integer)
    ended_on = db.Column(db.Integer)
    # url of the build results
    results = db.Column(db.Text)
    # status as returned by backend, see build.state for value explanation
    # (TODO: this would deserve an enum)
    status = db.Column(db.Integer)
    # memory requirements for backend builder
    memory_reqs = db.Column(db.Integer, default = constants.DEFAULT_BUILD_MEMORY)
    # maximum allowed time of build, build will fail if exceeded
    timeout = db.Column(db.Integer, default = constants.DEFAULT_BUILD_TIMEOUT)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    user = db.relationship('User', backref = db.backref('builds'))
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'))
    copr = db.relationship('Copr', backref = db.backref('builds'))

    @property
    def state(self):
        """Return text representation of status of this build"""
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
        """Find out if this build is cancelable.

        ATM, build is cancelable only if it wasn't grabbed by backend.
        """
        return self.state == 'pending'

class MockChroot(db.Model, Serializer):
    """Representation of mock chroot"""
    id = db.Column(db.Integer, primary_key = True)
    # fedora/epel/..., mandatory
    os_release = db.Column(db.String(50), nullable = False)
    # 18/rawhide/..., optional (mock chroot doesn't need to have this)
    os_version = db.Column(db.String(50), nullable = False)
    # x86_64/i686/..., mandatory
    arch = db.Column(db.String(50), nullable = False)
    is_active = db.Column(db.Boolean, default = True)

    @property
    def chroot_name(self):
        """Textual representation of name of this chroot"""
        if self.os_version:
            format_string = '{rel}-{ver}-{arch}'
        else:
            format_string = '{rel}-{arch}'
        return format_string.format(rel=self.os_release,
                                    ver=self.os_version,
                                    arch=self.arch)

class CoprChroot(db.Model, Serializer):
    """Representation of Copr<->MockChroot relation"""
    mock_chroot_id = db.Column(db.Integer, db.ForeignKey('mock_chroot.id'), primary_key = True)
    mock_chroot = db.relationship('MockChroot', backref = db.backref('copr_chroots'))
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'), primary_key = True)
    copr = db.relationship('Copr', backref = db.backref('copr_chroots',
                                                        single_parent=True,
                                                        cascade='all,delete,delete-orphan'))

class LegalFlag(db.Model, Serializer):
    id = db.Column(db.Integer, primary_key=True)
    # message from user who raised the flag (what he thinks is wrong)
    raise_message = db.Column(db.Text)
    # time of raising the flag as returned by int(time.time())
    raised_on = db.Column(db.Integer)
    # time of resolving the flag by admin as returned by int(time.time())
    resolved_on = db.Column(db.Integer)

    # relations
    copr_id = db.Column(db.Integer, db.ForeignKey('copr.id'), nullable=True)
    # cascade='all' means that we want to keep these even if copr is deleted
    copr = db.relationship('Copr', backref=db.backref('legal_flags', cascade='all'))
    # user who reported the problem
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reporter = db.relationship('User',
                               backref=db.backref('legal_flags_raised'),
                               foreign_keys=[reporter_id],
                               primaryjoin='LegalFlag.reporter_id==User.id')
    # admin who resolved the problem
    resolver_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    resolver = db.relationship('User',
                               backref=db.backref('legal_flags_resolved'),
                               foreign_keys=[resolver_id],
                               primaryjoin='LegalFlag.resolver_id==User.id')


class Action(db.Model, Serializer):
    """Representation of a custom action that needs backends cooperation/admin attention/..."""
    id = db.Column(db.Integer, primary_key=True)
    # delete, rename, ...; see helpers.ActionTypeEnum
    action_type = db.Column(db.Integer, nullable=False)
    # copr, ...; downcase name of class of modified object
    object_type = db.Column(db.String(20))
    # id of the modified object
    object_id = db.Column(db.Integer)
    # old and new values of the changed property
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    # result of the action, see helpers.BackendResultEnum
    result = db.Column(db.Integer, default=helpers.BackendResultEnum('waiting'))
    # optional message from the backend/whatever
    message = db.Column(db.Text)
    # time created as returned by int(time.time())
    created_on = db.Column(db.Integer)
    # time ended as returned by int(time.time())
    ended_on = db.Column(db.Integer)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        if self.action_type == helpers.ActionTypeEnum('delete'):
            return 'Deleting {0} {1}'.format(self.object_type, self.old_value)
        elif self.action_type == helpers.ActionTypeEnum('rename'):
            return 'Renaming {0} from {1} to {2}.'.format(self.object_type,
                                                          self.old_value,
                                                          self.new_value)
        elif self.action_type == helpers.ActionTypeEnum('legal-flag'):
            return 'Legal flag on copr {0}.'.format(self.old_value)

        return 'Action {0} on {1}, old value: {2}, new value: {3}.'.format(self.action_type,
                                                                           self.object_type,
                                                                           self.old_value,
                                                                           self.new_value)
