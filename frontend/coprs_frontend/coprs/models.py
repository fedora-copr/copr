import copy
import datetime
import os
import json
import base64
import uuid
from fnmatch import fnmatch

from sqlalchemy import outerjoin
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import column_property, validates
from six.moves.urllib.parse import urljoin
from libravatar import libravatar_url
import zlib

from copr_common.enums import ActionTypeEnum, BackendResultEnum, FailTypeEnum, ModuleStatusEnum, StatusEnum
from coprs import constants
from coprs import db
from coprs import helpers
from coprs import app

import itertools
import operator
from coprs.helpers import JSONEncodedDict

import gi
gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd


class CoprSearchRelatedData(object):
    def get_search_related_copr_id(self):
        raise "Not Implemented"


class _UserPublic(db.Model, helpers.Serializer):
    """
    Represents user of the copr frontend
    """
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)

    # unique username
    username = db.Column(db.String(100), nullable=False, unique=True)

    # is this user proven? proven users can modify builder memory and
    # timeout for single builds
    proven = db.Column(db.Boolean, default=False)

    # is this user admin of the system?
    admin = db.Column(db.Boolean, default=False)

    # can this user behave as someone else?
    proxy = db.Column(db.Boolean, default=False)

    # list of groups as retrieved from openid
    openid_groups = db.Column(JSONEncodedDict)


class _UserPrivate(db.Model, helpers.Serializer):
    """
    Records all the private information for a user.
    """
    # id (primary key + foreign key)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True,
            nullable=False)

    # email
    mail = db.Column(db.String(150), nullable=False)

    # optional timezone
    timezone = db.Column(db.String(50), nullable=True)

    # stuff for the cli interface
    api_login = db.Column(db.String(40), nullable=False, default="abc")
    api_token = db.Column(db.String(40), nullable=False, default="abc")
    api_token_expiration = db.Column(
        db.Date, nullable=False, default=datetime.date(2000, 1, 1))


class User(db.Model, helpers.Serializer):
    __table__ = outerjoin(_UserPublic.__table__, _UserPrivate.__table__)
    id = column_property(_UserPublic.__table__.c.id, _UserPrivate.__table__.c.user_id)

    @property
    def name(self):
        """
        Return the short username of the user, e.g. bkabrda
        """

        return self.username

    def permissions_for_copr(self, copr):
        """
        Get permissions of this user for the given copr.
        Caches the permission during one request,
        so use this if you access them multiple times
        """

        if not hasattr(self, "_permissions_for_copr"):
            self._permissions_for_copr = {}
        if copr.name not in self._permissions_for_copr:
            self._permissions_for_copr[copr.name] = (
                CoprPermission.query
                .filter_by(user=self)
                .filter_by(copr=copr)
                .first()
            )
        return self._permissions_for_copr[copr.name]

    def can_build_in(self, copr):
        """
        Determine if this user can build in the given copr.
        """
        can_build = False
        if copr.user_id == self.id:
            can_build = True
        if (self.permissions_for_copr(copr) and
                self.permissions_for_copr(copr).copr_builder ==
                helpers.PermissionEnum("approved")):

            can_build = True

        # a bit dirty code, here we access flask.session object
        if copr.group is not None and \
                copr.group.fas_name in self.user_teams:
            return True

        return can_build

    @property
    def user_teams(self):
        if self.openid_groups and 'fas_groups' in self.openid_groups:
            return self.openid_groups['fas_groups']
        else:
            return []

    @property
    def user_groups(self):
        return Group.query.filter(Group.fas_name.in_(self.user_teams)).all()

    def can_build_in_group(self, group):
        """
        :type group: Group
        """
        if group.fas_name in self.user_teams:
            return True
        else:
            return False

    def can_edit(self, copr):
        """
        Determine if this user can edit the given copr.
        """

        if copr.user == self or self.admin:
            return True
        if (self.permissions_for_copr(copr) and
                self.permissions_for_copr(copr).copr_admin ==
                helpers.PermissionEnum("approved")):

            return True

        if copr.group is not None and \
                copr.group.fas_name in self.user_teams:
            return True

        return False

    @property
    def serializable_attributes(self):
        # enumerate here to prevent exposing credentials
        return ["id", "name"]

    @property
    def coprs_count(self):
        """
        Get number of coprs for this user.
        """

        return (Copr.query.filter_by(user=self).
                filter_by(deleted=False).
                filter_by(group_id=None).
                count())

    @property
    def gravatar_url(self):
        """
        Return url to libravatar image.
        """

        try:
            return libravatar_url(email=self.mail, https=True)
        except IOError:
            return ""


class _CoprPublic(db.Model, helpers.Serializer, CoprSearchRelatedData):
    """
    Represents public part of a single copr (personal repo with builds, mock
    chroots, etc.).
    """

    __tablename__ = "copr"
    __table_args__ = (
        db.Index('copr_name_group_id_idx', 'name', 'group_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    # name of the copr, no fancy chars (checked by forms)
    name = db.Column(db.String(100), nullable=False)
    homepage = db.Column(db.Text)
    contact = db.Column(db.Text)
    # string containing urls of additional repos (separated by space)
    # that this copr will pull dependencies from
    repos = db.Column(db.Text)
    # time of creation as returned by int(time.time())
    created_on = db.Column(db.Integer)
    # description and instructions given by copr owner
    description = db.Column(db.Text)
    instructions = db.Column(db.Text)
    deleted = db.Column(db.Boolean, default=False)
    playground = db.Column(db.Boolean, default=False)

    # should copr run `createrepo` each time when build packages are changed
    auto_createrepo = db.Column(db.Boolean, default=True)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))
    forked_from_id = db.Column(db.Integer, db.ForeignKey("copr.id"))

    # enable networking for the builds by default
    build_enable_net = db.Column(db.Boolean, default=True,
                                 server_default="1", nullable=False)

    unlisted_on_hp = db.Column(db.Boolean, default=False, nullable=False)

    # information for search index updating
    latest_indexed_data_update = db.Column(db.Integer)

    # builds and the project are immune against deletion
    persistent = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    # if backend deletion script should be run for the project's builds
    auto_prune = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    # use mock's bootstrap container feature
    use_bootstrap_container = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    # if chroots for the new branch should be auto-enabled and populated from rawhide ones
    follow_fedora_branching = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    # scm integration properties
    scm_repo_url = db.Column(db.Text)
    scm_api_type = db.Column(db.Text)

    # temporary project if non-null
    delete_after = db.Column(db.DateTime, index=True, nullable=True)

    __mapper_args__ = {
        "order_by": created_on.desc()
    }


class _CoprPrivate(db.Model, helpers.Serializer):
    """
    Represents private part of a single copr (personal repo with builds, mock
    chroots, etc.).
    """

    __table_args__ = (
        db.Index('copr_private_webhook_secret', 'webhook_secret'),
    )

    # copr relation
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), index=True,
            nullable=False, primary_key=True)

    # a secret to be used for webhooks authentication
    webhook_secret = db.Column(db.String(100))

    # remote Git sites auth info
    scm_api_auth_json = db.Column(db.Text)


class Copr(db.Model, helpers.Serializer):
    """
    Represents private a single copr (personal repo with builds, mock chroots,
    etc.).
    """

    # This model doesn't have a single corresponding database table - so please
    # define any new Columns in _CoprPublic or _CoprPrivate models!
    __table__ = outerjoin(_CoprPublic.__table__, _CoprPrivate.__table__)
    id = column_property(
        _CoprPublic.__table__.c.id,
        _CoprPrivate.__table__.c.copr_id
    )

    # relations
    user = db.relationship("User", backref=db.backref("coprs"))
    group = db.relationship("Group", backref=db.backref("groups"))
    mock_chroots = association_proxy("copr_chroots", "mock_chroot")
    forked_from = db.relationship("Copr",
            remote_side=_CoprPublic.id,
            foreign_keys=[_CoprPublic.forked_from_id],
            backref=db.backref("forks"))

    @property
    def main_dir(self):
        """
        Return main copr dir for a Copr
        """
        return CoprDir.query.filter(CoprDir.copr_id==self.id).filter(CoprDir.main==True).one()

    @property
    def scm_api_auth(self):
        if not self.scm_api_auth_json:
            return {}
        return json.loads(self.scm_api_auth_json)

    @property
    def is_a_group_project(self):
        """
        Return True if copr belongs to a group
        """
        return self.group is not None

    @property
    def owner(self):
        """
        Return owner (user or group) of this copr
        """
        return self.group if self.is_a_group_project else self.user

    @property
    def owner_name(self):
        """
        Return @group.name for a copr owned by a group and user.name otherwise
        """
        return self.group.at_name if self.is_a_group_project else self.user.name

    @property
    def repos_list(self):
        """
        Return repos of this copr as a list of strings
        """
        return self.repos.split()

    @property
    def active_chroots(self):
        """
        Return list of active mock_chroots of this copr
        """
        return filter(lambda x: x.is_active, self.mock_chroots)

    @property
    def active_copr_chroots(self):
        """
        :rtype: list of CoprChroot
        """
        return [c for c in self.copr_chroots if c.is_active]

    @property
    def active_chroots_sorted(self):
        """
        Return list of active mock_chroots of this copr
        """
        return sorted(self.active_chroots, key=lambda ch: ch.name)

    @property
    def outdated_chroots(self):
        return [chroot for chroot in self.copr_chroots if chroot.delete_after]

    @property
    def active_chroots_grouped(self):
        """
        Return list of active mock_chroots of this copr
        """
        chroots = [("{} {}".format(c.os_release, c.os_version), c.arch) for c in self.active_chroots_sorted]
        output = []
        for os, chs in itertools.groupby(chroots, operator.itemgetter(0)):
            output.append((os, [ch[1] for ch in chs]))

        return output

    @property
    def build_count(self):
        """
        Return number of builds in this copr
        """
        return len(self.builds)

    @property
    def disable_createrepo(self):
        return not self.auto_createrepo

    @disable_createrepo.setter
    def disable_createrepo(self, value):
        self.auto_createrepo = not bool(value)

    @property
    def devel_mode(self):
        return self.disable_createrepo

    @property
    def modified_chroots(self):
        """
        Return list of chroots which has been modified
        """
        modified_chroots = []
        for chroot in self.copr_chroots:
            if ((chroot.buildroot_pkgs or chroot.repos
                 or chroot.with_opts or chroot.without_opts)
                    and chroot.is_active):
                modified_chroots.append(chroot)
        return modified_chroots

    def is_release_arch_modified(self, name_release, arch):
        if "{}-{}".format(name_release, arch) in \
                [chroot.name for chroot in self.modified_chroots]:
            return True
        return False

    @property
    def full_name(self):
        return "{}/{}".format(self.owner_name, self.name)

    @property
    def repo_name(self):
        return "{}-{}".format(self.owner_name, self.main_dir.name)

    @property
    def repo_url(self):
        return "/".join([app.config["BACKEND_BASE_URL"],
                         u"results",
                         self.main_dir.full_name])

    @property
    def repo_id(self):
        return "-".join([self.owner_name.replace("@", "group_"), self.name])

    @property
    def modules_url(self):
        return "/".join([self.repo_url, "modules"])

    def to_dict(self, private=False, show_builds=True, show_chroots=True):
        result = {}
        for key in ["id", "name", "description", "instructions"]:
            result[key] = str(copy.copy(getattr(self, key)))
        result["owner"] = self.owner_name
        return result

    @property
    def still_forking(self):
        return bool(Action.query.filter(Action.result == BackendResultEnum("waiting"))
                    .filter(Action.action_type == ActionTypeEnum("fork"))
                    .filter(Action.new_value == self.full_name).all())

    def get_search_related_copr_id(self):
        return self.id

    @property
    def enable_net(self):
        return self.build_enable_net

    @enable_net.setter
    def enable_net(self, value):
        self.build_enable_net = value

    def new_webhook_secret(self):
        self.webhook_secret = str(uuid.uuid4())

    @property
    def delete_after_days(self):
        if self.delete_after is None:
            return None

        delta = self.delete_after - datetime.datetime.now()
        return delta.days if delta.days > 0 else 0

    @delete_after_days.setter
    def delete_after_days(self, days):
        if days is None or days == -1:
            self.delete_after = None
            return

        delete_after = datetime.datetime.now() + datetime.timedelta(days=days+1)
        delete_after = delete_after.replace(hour=0, minute=0, second=0, microsecond=0)
        self.delete_after = delete_after

    @property
    def delete_after_msg(self):
        if self.delete_after_days == 0:
            return "will be deleted ASAP"
        return "will be deleted after {} days".format(self.delete_after_days)

    @property
    def admin_mails(self):
        mails = [self.user.mail]
        for perm in self.copr_permissions:
            if perm.copr_admin == helpers.PermissionEnum('approved'):
                mails.append(perm.user.mail)
        return mails

class CoprPermission(db.Model, helpers.Serializer):
    """
    Association class for Copr<->Permission relation
    """

    # see helpers.PermissionEnum for possible values of the fields below
    # can this user build in the copr?
    copr_builder = db.Column(db.SmallInteger, default=0)
    # can this user serve as an admin? (-> edit and approve permissions)
    copr_admin = db.Column(db.SmallInteger, default=0)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), primary_key=True)
    user = db.relationship("User", backref=db.backref("copr_permissions"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), primary_key=True)
    copr = db.relationship("Copr", backref=db.backref("copr_permissions"))

    def set_permission(self, name, value):
        if name == 'admin':
            self.copr_admin = value
        elif name == 'builder':
            self.copr_builder = value
        else:
            raise KeyError("{0} is not a valid copr permission".format(name))

    def get_permission(self, name):
        if name == 'admin':
            return 0 if self.copr_admin is None else self.copr_admin
        if name == 'builder':
            return 0 if self.copr_builder is None else self.copr_builder
        raise KeyError("{0} is not a valid copr permission".format(name))


class CoprDir(db.Model):
    """
    Represents one of data directories for a copr.
    """
    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.Text, index=True)
    main = db.Column(db.Boolean, default=False, server_default="0", nullable=False)

    ownername = db.Column(db.Text, index=True, nullable=False)

    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), index=True, nullable=False)
    copr = db.relationship("Copr", backref=db.backref("dirs"))

    __table_args__ = (
        db.Index('only_one_main_copr_dir', copr_id, main,
                 unique=True, postgresql_where=(main==True)),

        db.UniqueConstraint('ownername', 'name',
                            name='ownername_copr_dir_uniq'),
    )

    def __init__(self, *args, **kwargs):
        if kwargs.get('copr') and not kwargs.get('ownername'):
            kwargs['ownername'] = kwargs.get('copr').owner_name
        super(CoprDir, self).__init__(*args, **kwargs)

    @property
    def full_name(self):
        return "{}/{}".format(self.copr.owner_name, self.name)

    @property
    def repo_name(self):
        return "{}-{}".format(self.copr.owner_name, self.name)

    @property
    def repo_url(self):
        return "/".join([app.config["BACKEND_BASE_URL"],
                         u"results", self.full_name])

    @property
    def repo_id(self):
        if self.copr.is_a_group_project:
            return "group_{}-{}".format(self.copr.group.name, self.name)
        else:
            return "{}-{}".format(self.copr.user.name, self.name)


class Package(db.Model, helpers.Serializer, CoprSearchRelatedData):
    """
    Represents a single package in a project_dir.
    """

    __table_args__ = (
        db.UniqueConstraint('copr_dir_id', 'name', name='packages_copr_dir_pkgname'),
        db.Index('package_webhook_sourcetype', 'webhook_rebuild', 'source_type'),
    )

    def __init__(self, *args, **kwargs):
        if kwargs.get('copr') and not kwargs.get('copr_dir'):
            kwargs['copr_dir'] = kwargs.get('copr').main_dir
        super(Package, self).__init__(*args, **kwargs)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Source of the build: type identifier
    source_type = db.Column(db.Integer, default=helpers.BuildSourceEnum("unset"))
    # Source of the build: description in json, example: git link, srpm url, etc.
    source_json = db.Column(db.Text)
    # True if the package is built automatically via webhooks
    webhook_rebuild = db.Column(db.Boolean, default=False)
    # enable networking during a build process
    enable_net = db.Column(db.Boolean, default=False, server_default="0", nullable=False)

    # don't keep more builds of this package per copr-dir
    max_builds = db.Column(db.Integer, index=True)

    @validates('max_builds')
    def validate_max_builds(self, field, value):
        return None if value == 0 else value

    builds = db.relationship("Build", order_by="Build.id")

    # relations
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), index=True)
    copr = db.relationship("Copr", backref=db.backref("packages"))

    copr_dir_id = db.Column(db.Integer, db.ForeignKey("copr_dir.id"), index=True)
    copr_dir = db.relationship("CoprDir", backref=db.backref("packages"))

    # comma-separated list of wildcards of chroot names that this package should
    # not be built against, e.g. "fedora-*, epel-*-i386"
    chroot_blacklist_raw = db.Column(db.Text)

    @property
    def dist_git_repo(self):
        return "{}/{}".format(self.copr_dir.full_name, self.name)

    @property
    def source_json_dict(self):
        if not self.source_json:
            return {}
        return json.loads(self.source_json)

    @property
    def source_type_text(self):
        return helpers.BuildSourceEnum(self.source_type)

    @property
    def has_source_type_set(self):
        """
        Package's source type (and source_json) is being derived from its first build, which works except
        for "link" and "upload" cases. Consider these being equivalent to source_type being unset.
        """
        return self.source_type and self.source_type_text != "link" and self.source_type_text != "upload"

    @property
    def dist_git_url(self):
        if "DIST_GIT_URL" in app.config:
            return "{}/{}.git".format(app.config["DIST_GIT_URL"], self.dist_git_repo)
        return None

    @property
    def dist_git_clone_url(self):
        if "DIST_GIT_CLONE_URL" in app.config:
            return "{}/{}.git".format(app.config["DIST_GIT_CLONE_URL"], self.dist_git_repo)
        else:
            return self.dist_git_url

    def last_build(self, successful=False):
        for build in reversed(self.builds):
            if not successful or build.state == "succeeded":
                return build
        return None

    def to_dict(self, with_latest_build=False, with_latest_succeeded_build=False, with_all_builds=False):
        package_dict = super(Package, self).to_dict()
        package_dict['source_type'] = helpers.BuildSourceEnum(package_dict['source_type'])

        if with_latest_build:
            build = self.last_build(successful=False)
            package_dict['latest_build'] = build.to_dict(with_chroot_states=True) if build else None
        if with_latest_succeeded_build:
            build = self.last_build(successful=True)
            package_dict['latest_succeeded_build'] = build.to_dict(with_chroot_states=True) if build else None
        if with_all_builds:
            package_dict['builds'] = [build.to_dict(with_chroot_states=True) for build in reversed(self.builds)]

        return package_dict

    def get_search_related_copr_id(self):
        return self.copr.id


    @property
    def chroot_blacklist(self):
        if not self.chroot_blacklist_raw:
            return []

        blacklisted = []
        for pattern in self.chroot_blacklist_raw.split(','):
            pattern = pattern.strip()
            if not pattern:
                continue
            blacklisted.append(pattern)

        return blacklisted


    @staticmethod
    def matched_chroot(chroot, patterns):
        for pattern in patterns:
            if fnmatch(chroot.name, pattern):
                return True
        return False


    @property
    def main_pkg(self):
        if self.copr_dir.main:
            return self

        main_pkg = Package.query.filter_by(
                name=self.name,
                copr_dir_id=self.copr.main_dir.id
        ).first()
        return main_pkg


    @property
    def chroots(self):
        chroots = list(self.copr.active_chroots)
        if not self.chroot_blacklist_raw:
            # no specific blacklist
            if self.copr_dir.main:
                return chroots
            return self.main_pkg.chroots

        filtered = [c for c in chroots if not self.matched_chroot(c, self.chroot_blacklist)]
        # We never want to filter everything, this is a misconfiguration.
        return filtered if filtered else chroots


class Build(db.Model, helpers.Serializer):
    """
    Representation of one build in one copr
    """

    SCM_COMMIT = 'commit'
    SCM_PULL_REQUEST = 'pull-request'

    __table_args__ = (db.Index('build_canceled', "canceled"),
                      db.Index('build_order', "is_background", "id"),
                      db.Index('build_filter', "source_type", "canceled"),
                      db.Index('build_canceled_is_background_source_status_id_idx', 'canceled', "is_background", "source_status", "id"),
                     )

    def __init__(self, *args, **kwargs):
        if kwargs.get('source_type') == helpers.BuildSourceEnum("custom"):
            source_dict = json.loads(kwargs['source_json'])
            if 'fedora-latest' in source_dict['chroot']:
                arch = source_dict['chroot'].rsplit('-', 2)[2]
                source_dict['chroot'] = \
                    MockChroot.latest_fedora_branched_chroot(arch=arch).name
            kwargs['source_json'] = json.dumps(source_dict)

        if kwargs.get('copr') and not kwargs.get('copr_dir'):
            kwargs['copr_dir'] = kwargs.get('copr').main_dir

        super(Build, self).__init__(*args, **kwargs)

    id = db.Column(db.Integer, primary_key=True)
    # single url to the source rpm, should not contain " ", "\n", "\t"
    pkgs = db.Column(db.Text)
    # built packages
    built_packages = db.Column(db.Text)
    # version of the srpm package got by rpm
    pkg_version = db.Column(db.Text)
    # was this build canceled by user?
    canceled = db.Column(db.Boolean, default=False)
    # list of space separated additional repos
    repos = db.Column(db.Text)
    # the three below represent time of important events for this build
    # as returned by int(time.time())
    submitted_on = db.Column(db.Integer, nullable=False)
    # directory name on backend with the srpm build results
    result_dir = db.Column(db.Text, default='', server_default='', nullable=False)
    # memory requirements for backend builder
    memory_reqs = db.Column(db.Integer, default=constants.DEFAULT_BUILD_MEMORY)
    # maximum allowed time of build, build will fail if exceeded
    timeout = db.Column(db.Integer, default=constants.DEFAULT_BUILD_TIMEOUT)
    # enable networking during a build process
    enable_net = db.Column(db.Boolean, default=False,
                           server_default="0", nullable=False)
    # Source of the build: type identifier
    source_type = db.Column(db.Integer, default=helpers.BuildSourceEnum("unset"))
    # Source of the build: description in json, example: git link, srpm url, etc.
    source_json = db.Column(db.Text)
    # Type of failure: type identifier
    fail_type = db.Column(db.Integer, default=FailTypeEnum("unset"))
    # background builds has lesser priority than regular builds.
    is_background = db.Column(db.Boolean, default=False, server_default="0", nullable=False)

    source_status = db.Column(db.Integer, default=StatusEnum("waiting"))
    srpm_url = db.Column(db.Text)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    user = db.relationship("User", backref=db.backref("builds"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), index=True)
    copr = db.relationship("Copr", backref=db.backref("builds"))
    package_id = db.Column(db.Integer, db.ForeignKey("package.id"), index=True)
    package = db.relationship("Package")

    chroots = association_proxy("build_chroots", "mock_chroot")

    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"))
    batch = db.relationship("Batch", backref=db.backref("builds"))

    module_id = db.Column(db.Integer, db.ForeignKey("module.id"), index=True)
    module = db.relationship("Module", backref=db.backref("builds"))

    copr_dir_id = db.Column(db.Integer, db.ForeignKey("copr_dir.id"), index=True)
    copr_dir = db.relationship("CoprDir", backref=db.backref("builds"))

    # scm integration properties
    scm_object_id = db.Column(db.Text)
    scm_object_type = db.Column(db.Text)
    scm_object_url = db.Column(db.Text)

    # method to call on build state change
    update_callback = db.Column(db.Text)

    @property
    def user_name(self):
        return self.user.name

    @property
    def group_name(self):
        return self.copr.group.name

    @property
    def copr_name(self):
        return self.copr.name

    @property
    def copr_dirname(self):
        return self.copr_dir.name

    @property
    def copr_full_dirname(self):
        return self.copr_dir.full_name

    @property
    def fail_type_text(self):
        return FailTypeEnum(self.fail_type)

    @property
    def repos_list(self):
        if self.repos is None:
            return list()
        else:
            return self.repos.split()

    @property
    def task_id(self):
        return str(self.id)

    @property
    def id_fixed_width(self):
        return "{:08d}".format(self.id)

    def get_import_log_urls(self, admin=False):
        logs = [self.import_log_url_backend]
        if admin:
            logs.append(self.import_log_url_distgit)
        return list(filter(None, logs))

    @property
    def import_log_url_distgit(self):
        if app.config["COPR_DIST_GIT_LOGS_URL"]:
            return "{}/{}.log".format(app.config["COPR_DIST_GIT_LOGS_URL"],
                                      self.task_id.replace('/', '_'))
        return None

    @property
    def import_log_url_backend(self):
        parts = ["results", self.copr.owner_name, self.copr_dirname,
                 "srpm-builds", self.id_fixed_width, "builder-live.log"]
        path = os.path.normpath(os.path.join(*parts))
        return urljoin(app.config["BACKEND_BASE_URL"], path)

    @property
    def source_json_dict(self):
        if not self.source_json:
            return {}
        return json.loads(self.source_json)

    @property
    def started_on(self):
        return self.min_started_on

    @property
    def min_started_on(self):
        mb_list = [chroot.started_on for chroot in
                   self.build_chroots if chroot.started_on]
        if len(mb_list) > 0:
            return min(mb_list)
        else:
            return None

    @property
    def ended_on(self):
        return self.max_ended_on

    @property
    def max_ended_on(self):
        if not self.build_chroots:
            return None
        if any(chroot.ended_on is None for chroot in self.build_chroots):
            return None
        return max(chroot.ended_on for chroot in self.build_chroots)

    @property
    def chroots_started_on(self):
        return {chroot.name: chroot.started_on for chroot in self.build_chroots}

    @property
    def chroots_ended_on(self):
        return {chroot.name: chroot.ended_on for chroot in self.build_chroots}

    @property
    def source_type_text(self):
        return helpers.BuildSourceEnum(self.source_type)

    @property
    def source_metadata(self):
        if self.source_json is None:
            return None

        try:
            return json.loads(self.source_json)
        except (TypeError, ValueError):
            return None

    @property
    def chroot_states(self):
        return map(lambda chroot: chroot.status, self.build_chroots)

    def get_chroots_by_status(self, statuses=None):
        """
        Get build chroots with states which present in `states` list
        If states == None, function returns build_chroots
        """
        chroot_states_map = dict(zip(self.build_chroots, self.chroot_states))
        if statuses is not None:
            statuses = set(statuses)
        else:
            return self.build_chroots

        return [
            chroot for chroot, status in chroot_states_map.items()
            if status in statuses
        ]

    @property
    def chroots_dict_by_name(self):
        return {b.name: b for b in self.build_chroots}

    @property
    def status(self):
        """
        Return build status.
        """
        if self.canceled:
            return StatusEnum("canceled")

        use_src_statuses = ["starting", "pending", "running", "failed"]
        if self.source_status in [StatusEnum(s) for s in use_src_statuses]:
            return self.source_status

        for state in ["running", "starting", "pending", "failed", "succeeded", "skipped", "forked", "waiting"]:
            if StatusEnum(state) in self.chroot_states:
                if state == "waiting":
                    return self.source_status
                else:
                    return StatusEnum(state)

        return None

    @property
    def state(self):
        """
        Return text representation of status of this build.
        """
        if self.status != None:
            return StatusEnum(self.status)
        return "unknown"

    @property
    def cancelable(self):
        """
        Find out if this build is cancelable.
        """
        return not self.finished and self.status != StatusEnum("starting")

    @property
    def repeatable(self):
        """
        Find out if this build is repeatable.

        Build is repeatable only if sources has been imported.
        """
        return self.source_status == StatusEnum("succeeded")

    @property
    def finished(self):
        """
        Find out if this build is in finished state.

        Build is finished only if all its build_chroots are in finished state or
        the build was canceled.
        """
        if self.canceled:
            return True
        if not self.build_chroots:
            # Not even SRPM is finished
            return False
        return all([chroot.finished for chroot in self.build_chroots])

    @property
    def persistent(self):
        """
        Find out if this build is persistent.

        This property is inherited from the project.
        """
        return self.copr.persistent

    @property
    def package_name(self):
        try:
            return self.package.name
        except:
            return None

    def to_dict(self, options=None, with_chroot_states=False):
        result = super(Build, self).to_dict(options)
        result["src_pkg"] = result["pkgs"]
        del result["pkgs"]
        del result["copr_id"]

        result['source_type'] = helpers.BuildSourceEnum(result['source_type'])
        result["state"] = self.state

        if with_chroot_states:
            result["chroots"] = {b.name: b.state for b in self.build_chroots}

        return result


class DistGitBranch(db.Model, helpers.Serializer):
    """
    1:N mapping: branch -> chroots
    """

    # Name of the branch used on dist-git machine.
    name = db.Column(db.String(50), primary_key=True)


class MockChroot(db.Model, helpers.Serializer):
    """
    Representation of mock chroot
    """

    __table_args__ = (
        db.UniqueConstraint('os_release', 'os_version', 'arch', name='mock_chroot_uniq'),
    )

    id = db.Column(db.Integer, primary_key=True)
    # fedora/epel/..., mandatory
    os_release = db.Column(db.String(50), nullable=False)
    # 18/rawhide/..., optional (mock chroot doesn"t need to have this)
    os_version = db.Column(db.String(50), nullable=False)
    # x86_64/i686/..., mandatory
    arch = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    # Reference branch name
    distgit_branch_name  = db.Column(db.String(50),
                                     db.ForeignKey("dist_git_branch.name"),
                                     nullable=False)

    distgit_branch = db.relationship("DistGitBranch",
            backref=db.backref("chroots"))

    # After a mock_chroot is EOLed, this is set to true so that copr_prune_results
    # will skip all projects using this chroot
    final_prunerepo_done = db.Column(db.Boolean, default=False, server_default="0", nullable=False)

    @classmethod
    def latest_fedora_branched_chroot(cls, arch='x86_64'):
        return (cls.query
                .filter(cls.is_active == True)
                .filter(cls.os_release == 'fedora')
                .filter(cls.os_version != 'rawhide')
                .filter(cls.arch == arch)
                .order_by(cls.os_version.desc())
                .first())

    @property
    def name(self):
        """
        Textual representation of name of this chroot
        """
        return "{}-{}-{}".format(self.os_release, self.os_version, self.arch)

    @property
    def name_release(self):
        """
        Textual representation of name of this or release
        """
        return "{}-{}".format(self.os_release, self.os_version)

    @property
    def os(self):
        """
        Textual representation of the operating system name
        """
        return "{0} {1}".format(self.os_release, self.os_version)

    @property
    def serializable_attributes(self):
        attr_list = super(MockChroot, self).serializable_attributes
        attr_list.extend(["name", "os"])
        return attr_list


class CoprChroot(db.Model, helpers.Serializer):
    """
    Representation of Copr<->MockChroot relation
    """

    buildroot_pkgs = db.Column(db.Text)
    repos = db.Column(db.Text, default="", server_default="", nullable=False)
    mock_chroot_id = db.Column(
        db.Integer, db.ForeignKey("mock_chroot.id"), primary_key=True)
    mock_chroot = db.relationship(
        "MockChroot", backref=db.backref("copr_chroots"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), primary_key=True)
    copr = db.relationship("Copr",
                           backref=db.backref(
                               "copr_chroots",
                               single_parent=True,
                               cascade="all,delete,delete-orphan"))

    comps_zlib = db.Column(db.LargeBinary(), nullable=True)
    comps_name = db.Column(db.String(127), nullable=True)

    module_md_zlib = db.Column(db.LargeBinary(), nullable=True)
    module_md_name = db.Column(db.String(127), nullable=True)

    with_opts = db.Column(db.Text, default="", server_default="", nullable=False)
    without_opts = db.Column(db.Text, default="", server_default="", nullable=False)

    # Once mock_chroot gets EOL, copr_chroots are going to be deleted
    # if their owner doesn't extend their time span
    delete_after = db.Column(db.DateTime, index=True)
    delete_notify = db.Column(db.DateTime, index=True)

    def update_comps(self, comps_xml):
        if isinstance(comps_xml, str):
            data = comps_xml.encode("utf-8")
        else:
            data = comps_xml
        self.comps_zlib = zlib.compress(data)

    def update_module_md(self, module_md_yaml):
        if isinstance(module_md_yaml, str):
            data = module_md_yaml.encode("utf-8")
        else:
            data = module_md_yaml
        self.module_md_zlib = zlib.compress(data)

    @property
    def buildroot_pkgs_list(self):
        return (self.buildroot_pkgs or "").split()

    @property
    def repos_list(self):
        return (self.repos or "").split()

    @property
    def comps(self):
        if self.comps_zlib:
            return zlib.decompress(self.comps_zlib).decode("utf-8")

    @property
    def module_md(self):
        if self.module_md_zlib:
            return zlib.decompress(self.module_md_zlib).decode("utf-8")

    @property
    def comps_len(self):
        if self.comps_zlib:
            return len(zlib.decompress(self.comps_zlib))
        else:
            return 0

    @property
    def module_md_len(self):
        if self.module_md_zlib:
            return len(zlib.decompress(self.module_md_zlib))
        else:
            return 0

    @property
    def name(self):
        return self.mock_chroot.name

    @property
    def is_active(self):
        return self.mock_chroot.is_active

    @property
    def delete_after_days(self):
        if not self.delete_after:
            return None
        now = datetime.datetime.now()
        return (self.delete_after - now).days

    def to_dict(self):
        options = {"__columns_only__": [
            "buildroot_pkgs", "repos", "comps_name", "copr_id", "with_opts", "without_opts"
        ]}
        d = super(CoprChroot, self).to_dict(options=options)
        d["mock_chroot"] = self.mock_chroot.name
        return d


class BuildChroot(db.Model, helpers.Serializer):
    """
    Representation of Build<->MockChroot relation
    """

    __table_args__ = (db.Index('build_chroot_status_started_on_idx', "status", "started_on"),)

    mock_chroot_id = db.Column(db.Integer, db.ForeignKey("mock_chroot.id"),
                               primary_key=True)
    mock_chroot = db.relationship("MockChroot", backref=db.backref("builds"))
    build_id = db.Column(db.Integer, db.ForeignKey("build.id"),
                         primary_key=True)
    build = db.relationship("Build", backref=db.backref("build_chroots"))
    git_hash = db.Column(db.String(40))
    status = db.Column(db.Integer, default=StatusEnum("waiting"))

    started_on = db.Column(db.Integer, index=True)
    ended_on = db.Column(db.Integer, index=True)

    # directory name on backend with build results
    result_dir = db.Column(db.Text, default='', server_default='', nullable=False)

    build_requires = db.Column(db.Text)

    @property
    def name(self):
        """
        Textual representation of name of this chroot
        """
        return self.mock_chroot.name

    @property
    def state(self):
        """
        Return text representation of status of this build chroot
        """
        if self.status is not None:
            return StatusEnum(self.status)
        return "unknown"

    @property
    def finished(self):
        return (self.state in ["succeeded", "forked", "canceled", "skipped", "failed"])

    @property
    def task_id(self):
        return "{}-{}".format(self.build_id, self.name)

    @property
    def dist_git_url(self):
        if app.config["DIST_GIT_URL"]:
            if self.state == "forked":
                copr_dirname = self.build.copr.forked_from.main_dir.full_name
            else:
                copr_dirname = self.build.copr_dir.full_name
            return "{}/{}/{}.git/commit/?id={}".format(app.config["DIST_GIT_URL"],
                                                copr_dirname,
                                                self.build.package.name,
                                                self.git_hash)
        return None

    @property
    def result_dir_url(self):
        if not self.result_dir:
            return None
        return urljoin(app.config["BACKEND_BASE_URL"], os.path.join(
            "results", self.build.copr_dir.full_name, self.name, self.result_dir, ""))


class LegalFlag(db.Model, helpers.Serializer):
    id = db.Column(db.Integer, primary_key=True)
    # message from user who raised the flag (what he thinks is wrong)
    raise_message = db.Column(db.Text)
    # time of raising the flag as returned by int(time.time())
    raised_on = db.Column(db.Integer)
    # time of resolving the flag by admin as returned by int(time.time())
    resolved_on = db.Column(db.Integer)

    # relations
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), nullable=True)
    # cascade="all" means that we want to keep these even if copr is deleted
    copr = db.relationship(
        "Copr", backref=db.backref("legal_flags", cascade="all"))
    # user who reported the problem
    reporter_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    reporter = db.relationship("User",
                               backref=db.backref("legal_flags_raised"),
                               foreign_keys=[reporter_id],
                               primaryjoin="LegalFlag.reporter_id==User.id")
    # admin who resolved the problem
    resolver_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True)
    resolver = db.relationship("User",
                               backref=db.backref("legal_flags_resolved"),
                               foreign_keys=[resolver_id],
                               primaryjoin="LegalFlag.resolver_id==User.id")


class Action(db.Model, helpers.Serializer):
    """
    Representation of a custom action that needs
    backends cooperation/admin attention/...
    """

    id = db.Column(db.Integer, primary_key=True)
    # see ActionTypeEnum
    action_type = db.Column(db.Integer, nullable=False)
    # copr, ...; downcase name of class of modified object
    object_type = db.Column(db.String(20))
    # id of the modified object
    object_id = db.Column(db.Integer)
    # old and new values of the changed property
    old_value = db.Column(db.String(255))
    new_value = db.Column(db.String(255))
    # additional data
    data = db.Column(db.Text)
    # result of the action, see BackendResultEnum
    result = db.Column(
        db.Integer, default=BackendResultEnum("waiting"))
    # optional message from the backend/whatever
    message = db.Column(db.Text)
    # time created as returned by int(time.time())
    created_on = db.Column(db.Integer)
    # time ended as returned by int(time.time())
    ended_on = db.Column(db.Integer)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        if self.action_type == ActionTypeEnum("delete"):
            return "Deleting {0} {1}".format(self.object_type, self.old_value)
        elif self.action_type == ActionTypeEnum("legal-flag"):
            return "Legal flag on copr {0}.".format(self.old_value)

        return "Action {0} on {1}, old value: {2}, new value: {3}.".format(
            self.action_type, self.object_type, self.old_value, self.new_value)

    def to_dict(self, **kwargs):
        d = super(Action, self).to_dict()
        if d.get("object_type") == "module":
            module = Module.query.filter(Module.id == d["object_id"]).first()
            data = json.loads(d["data"])
            data.update({
                "projectname": module.copr.name,
                "ownername": module.copr.owner_name,
                "modulemd_b64": module.yaml_b64,
            })
            d["data"] = json.dumps(data)
        return d


class Krb5Login(db.Model, helpers.Serializer):
    """
    Represents additional user information for kerberos authentication.
    """

    __tablename__ = "krb5_login"

    # FK to User table
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # 'string' from 'copr.conf' from KRB5_LOGIN[string]
    config_name = db.Column(db.String(30), nullable=False, primary_key=True)

    # krb's primary, i.e. 'username' from 'username@EXAMPLE.COM'
    primary = db.Column(db.String(80), nullable=False, primary_key=True)

    user = db.relationship("User", backref=db.backref("krb5_logins"))


class CounterStat(db.Model, helpers.Serializer):
    """
    Generic store for simple statistics.
    """

    name = db.Column(db.String(127), primary_key=True)
    counter_type = db.Column(db.String(30))

    counter = db.Column(db.Integer, default=0, server_default="0")


class Group(db.Model, helpers.Serializer):

    """
    Represents FAS groups and their aliases in Copr
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127))

    # TODO: add unique=True
    fas_name = db.Column(db.String(127))

    @property
    def at_name(self):
        return u"@{}".format(self.name)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        return "{} (fas: {})".format(self.name, self.fas_name)


class Batch(db.Model):
    id = db.Column(db.Integer, primary_key=True)


class Module(db.Model, helpers.Serializer):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    stream = db.Column(db.String(100), nullable=False)
    version = db.Column(db.BigInteger, nullable=False)
    summary = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_on = db.Column(db.Integer, nullable=True)

    # When someone submits YAML (not generate one on the copr modules page), we might want to use that exact file.
    # Yaml produced by deconstructing into pieces and constructed back can look differently,
    # which is not desirable (Imo)
    #
    # Also if there are fields which are not covered by this model, we will be able to add them in the future
    # and fill them with data from this blob
    yaml_b64 = db.Column(db.Text)

    # relations
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))
    copr = db.relationship("Copr", backref=db.backref("modules"))

    __table_args__ = (
        db.UniqueConstraint("copr_id", "name", "stream", "version", name="copr_name_stream_version_uniq"),
    )

    @property
    def yaml(self):
        return base64.b64decode(self.yaml_b64)

    @property
    def modulemd(self):
        mmd = Modulemd.ModuleStream()
        mmd.import_from_string(self.yaml.decode("utf-8"))
        return mmd

    @property
    def nsv(self):
        return "-".join([self.name, self.stream, str(self.version)])

    @property
    def full_name(self):
        return "{}/{}".format(self.copr.full_name, self.nsv)

    @property
    def action(self):
        return Action.query.filter(Action.object_type == "module").filter(Action.object_id == self.id).first()

    @property
    def status(self):
        """
        Return numeric representation of status of this build
        """
        if any(b for b in self.builds if b.status == StatusEnum("failed")):
            return ModuleStatusEnum("failed")
        return self.action.result if self.action else ModuleStatusEnum("pending")

    @property
    def state(self):
        """
        Return text representation of status of this build
        """
        return ModuleStatusEnum(self.status)

    @property
    def rpm_filter(self):
        return self.modulemd.get_rpm_filter().get()

    @property
    def rpm_api(self):
        return self.modulemd.get_rpm_api().get()

    @property
    def profiles(self):
        return {k: v.get_rpms().get() for k, v in self.modulemd.get_profiles().items()}


class BuildsStatistics(db.Model):
    time = db.Column(db.Integer, primary_key=True)
    stat_type = db.Column(db.Text, primary_key=True)
    running = db.Column(db.Integer)
    pending = db.Column(db.Integer)
