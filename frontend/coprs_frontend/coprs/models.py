"""
Copr Frontend database layout, see the ER diagram:
https://docs.pagure.org/copr.copr/_images/db-erd.png
"""

import copy
import datetime
from fnmatch import fnmatch
import itertools
import json
import base64
import operator
import os
from urllib.parse import urljoin
import uuid
import time
import zlib

import modulemd_tools.yaml

from sqlalchemy import outerjoin, text
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import column_property, validates
from sqlalchemy.event import listens_for
from libravatar import libravatar_url

from flask import url_for

from copr_common.enums import (ActionTypeEnum, BackendResultEnum, FailTypeEnum,
                               ModuleStatusEnum, StatusEnum, DefaultActionPriorityEnum)
from coprs import db
from coprs import helpers
from coprs import app

from coprs.helpers import JSONEncodedDict, ChrootDeletionStatus


# Pylint Specifics for models.py:
# - too-few-public-methods: models are often very trivial classes
# pylint: disable=too-few-public-methods

class CoprSearchRelatedData(object):
    def get_search_related_copr_id(self):
        raise NotImplementedError


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

    # List of groups as retrieved from openid.
    # The name `openid_groups` is misleading because we now support more
    # group authorities (e.g. LDAP) than just OpenID. Whatever group authority
    # is used, the `openid_groups` variable needs to be in the  following format
    #     openid_groups = {"fas_groups": ["foo", "bar", "baz"]}
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

    @property
    def copr_permissions(self):
        """
        Filter-out the permissions for deleted projects from
        self.copr_permissions_unfiltered.
        """
        return [perm for perm in self.copr_permissions_unfiltered
                if not perm.copr.deleted]

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
        if self.admin:
            return True
        if copr.group:
            if self.can_build_in_group(copr.group):
                return True
        elif copr.user_id == self.id:
            return True
        if permissions := self.permissions_for_copr(copr):
            builder, admin = permissions.copr_builder, permissions.copr_admin
            if helpers.PermissionEnum("approved") in (builder, admin):
                return True
        return False

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

    def can_edit(self, copr, ignore_admin=False):
        """
        Determine if this user can edit the given copr.
        """
        # People can obviously edit their personal projects, but the person who
        # created a group project doesn't get any exclusive permissions to it.
        # We still need to validate their group membership every time.
        if not copr.group and copr.user == self:
            return True

        # Copr maintainers can edit every project
        if not ignore_admin and self.admin:
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

    def score_for_copr(self, copr):
        """
        Check if the `user` has voted for this `copr` and return 1 if it was
        upvoted, -1 if it was downvoted and 0 if the `user` haven't voted for
        it yet.
        """
        query = db.session.query(CoprScore)
        query = query.filter(CoprScore.copr_id == copr.id)
        query = query.filter(CoprScore.user_id == self.id)
        score = query.first()
        return score.score if score else 0


class PinnedCoprs(db.Model, helpers.Serializer):
    """
    Representation of User or Group <-> Copr relation
    """
    id = db.Column(db.Integer, primary_key=True)

    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"), nullable=True, index=True)
    position = db.Column(db.Integer, nullable=False)

    copr = db.relationship("Copr")
    user = db.relationship("User")
    group = db.relationship("Group")


class CoprScore(db.Model, helpers.Serializer):
    """
    Users can upvote or downvote projects
    """
    id = db.Column(db.Integer, primary_key=True)
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)

    copr = db.relationship("Copr")
    user = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("copr_id", "user_id",
                            name="copr_score_copr_id_user_id_uniq"),
    )

_group_unique_where = text("deleted is not true and group_id is not null")
_user_unique_where = text("deleted is not true and group_id is null")

class _CoprPublic(db.Model, helpers.Serializer):
    """
    Represents public part of a single copr (personal repo with builds, mock
    chroots, etc.).
    """

    __tablename__ = "copr"
    __table_args__ = (
        db.Index('copr_name_group_id_idx', 'name', 'group_id'),
        db.Index('copr_deleted_name', 'deleted', 'name'),
        db.Index("copr_name_in_group_uniq",
                 "group_id", "name",
                 unique=True,
                 postgresql_where=_group_unique_where,
                 sqlite_where=_group_unique_where),
        db.Index("copr_name_for_user_uniq",
                 "user_id", "name",
                 unique=True,
                 postgresql_where=_user_unique_where,
                 sqlite_where=_user_unique_where),
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
    auto_createrepo = db.Column(db.Boolean, default=True, nullable=False)

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

    isolation = db.Column(db.Text, default="default")

    bootstrap = db.Column(db.Text, default="default")

    # if chroots for the new branch should be auto-enabled and populated from rawhide ones
    follow_fedora_branching = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    # scm integration properties
    scm_repo_url = db.Column(db.Text)
    scm_api_type = db.Column(db.Text)

    # temporary project if non-null
    delete_after = db.Column(db.DateTime, index=True, nullable=True)

    multilib = db.Column(db.Boolean, default=False, nullable=False, server_default="0")
    module_hotfixes = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    runtime_dependencies = db.Column(db.Text)

    # optional tools to run after build
    fedora_review = db.Column(db.Boolean, default=False, nullable=False, server_default="0")

    appstream = db.Column(db.Boolean, default=True, nullable=False, server_default="1")

    # string containing forge projects (separated by whitespace)
    # allowed to build in this Copr via Packit
    packit_forge_projects_allowed = db.Column(db.Text)


class _CoprPrivate(db.Model, helpers.Serializer):
    """
    Represents private part of a single copr (personal repo with builds, mock
    chroots, etc.).
    """

    __table_args__ = (
        db.Index('copr_private_webhook_secret', 'webhook_secret'),
    )

    # copr relation
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), nullable=False,
                        primary_key=True)

    # a secret to be used for webhooks authentication
    webhook_secret = db.Column(db.String(100))

    # remote Git sites auth info
    scm_api_auth_json = db.Column(db.Text)


class Copr(db.Model, helpers.Serializer, CoprSearchRelatedData):
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
            backref=db.backref("all_forks"))

    @property
    def forks(self):
        return [fork for fork in self.all_forks if not fork.deleted]

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
        result = self.repos or ""
        return result.split()

    @property
    def active_chroots(self):
        """
        Return list of active mock_chroots of this copr
        """
        return [cc.mock_chroot for cc in self.active_copr_chroots]

    @property
    def enable_permissible_copr_chroots(self):
        """
        Return the list of not-yet-deleted (includes EOLed) copr_chroots
        assigned to this copr.
        """
        permissible_states = [
            ChrootDeletionStatus("active"),
            ChrootDeletionStatus("preserved"),
        ]
        return [cc for cc in self.copr_chroots
                if cc.delete_status in permissible_states]

    @property
    def enable_permissible_chroots(self):
        """
        Return the list of not-yet-deleted (includes EOLed) mock_chroots
        assigned to this copr.
        """
        return [cc.mock_chroot for cc in self.enable_permissible_copr_chroots]


    @property
    def active_multilib_chroots(self):
        """
        Return list of active mock_chroots which have the 32bit multilib
        counterpart.
        """
        chroot_names = [chroot.name for chroot in self.active_chroots]

        found_chroots = []
        for chroot in self.active_chroots:
            if chroot.arch not in MockChroot.multilib_pairs:
                continue

            counterpart = "{}-{}-{}".format(chroot.os_release,
                                            chroot.os_version,
                                            MockChroot.multilib_pairs[chroot.arch])
            if counterpart in chroot_names:
                found_chroots.append(chroot)

        return found_chroots


    @property
    def active_copr_chroots(self):
        """
        :rtype: list of CoprChroot
        """
        return [c for c in self.copr_chroots if c.is_active and not c.deleted]

    @property
    def active_chroots_sorted(self):
        """
        Return list of active mock_chroots of this copr
        """
        return sorted(self.active_chroots, key=lambda ch: ch.name)

    @property
    def outdated_chroots(self):
        return sorted([chroot for chroot in self.copr_chroots
                       if chroot.delete_after and not chroot.deleted],
                      key=lambda ch: ch.name)

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
        Return list of chroots which has been modified in ChrootForm.
        """
        modified_chroots = {}
        def _set(chroot, attribute, value, check=None):
            if check is not None and not check:
                return
            if not value:
                return
            if chroot not in modified_chroots:
                modified_chroots[chroot] = {}
            modified_chroots[chroot][attribute] = value

        for chroot in self.active_copr_chroots:
            _set(chroot.name,
                 "Additional buildroot packages",
                 ", ".join(chroot.buildroot_pkgs_list))
            _set(chroot.name,
                 "Build time repositories",
                 ", ".join(chroot.repos_list))

            mock_opts = []
            for opt in chroot.with_opts.strip().split():
                mock_opts += ["--with " + opt]
            for opt in chroot.without_opts.strip().split():
                mock_opts += ["--without " + opt]
            _set(chroot.name,
                 "Mock options",
                 " ".join(mock_opts))
            _set(chroot.name,
                 "Module setup commands",
                 chroot.module_toggle)
            _set(chroot.name,
                 "Bootstrap overridden as",
                 chroot.bootstrap,
                 chroot.bootstrap_changed)
            _set(chroot.name,
                 "Isolation set to",
                 chroot.isolation,
                 chroot.isolation and chroot.isolation != 'unchanged')

        return modified_chroots

    def is_release_arch_modified(self, name_release, arch):
        return "{}-{}".format(name_release, arch) in self.modified_chroots.keys()

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
                         self.full_name])

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

    @property
    def runtime_deps(self):
        """
        Return a list of runtime dependencies"
        """
        dependencies = set()
        if self.runtime_dependencies:
            for dep in self.runtime_dependencies.split():
                if not dep:
                    continue
                dependencies.add(dep)

        return list(dependencies)

    @property
    def votes(self):
        query = db.session.query(CoprScore)
        query = query.filter(CoprScore.copr_id == self.id)
        return query

    @property
    def upvotes(self):
        return self.votes.filter(CoprScore.score == 1).count()

    @property
    def downvotes(self):
        return self.votes.filter(CoprScore.score == -1).count()

    @property
    def score(self):
        return sum([self.upvotes, self.downvotes * -1])

    @property
    def packit_forge_projects_allowed_list(self):
        """
        Return forge projects allowed to build in this copr via Packit
         as a list of strings.
        """
        projects = self.packit_forge_projects_allowed or ""
        return projects.split()


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
    user = db.relationship("User",
                           backref=db.backref("copr_permissions_unfiltered"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), primary_key=True,
                        index=True)
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
    main = db.Column(db.Boolean, index=True, default=False, server_default="0", nullable=False)

    ownername = db.Column(db.Text, index=True, nullable=False)

    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), index=True, nullable=False)
    copr = db.relationship("Copr", backref=db.backref("dirs"))

    __table_args__ = (
        db.Index('only_one_main_copr_dir', copr_id, main,
                 unique=True, postgresql_where=(main),
                 sqlite_where=(main)),

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
        db.Index('package_copr_id_name', 'copr_id', 'name', unique=True),
        db.Index('package_webhook_sourcetype', 'webhook_rebuild', 'source_type'),
    )

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

    # comma-separated list of wildcards of chroot names that this package should
    # not be built against, e.g. "fedora-*, epel-*-i386"
    chroot_denylist_raw = db.Column(db.Text)

    @property
    def dist_git_repo(self):
        return "{}/{}".format(self.copr.full_name, self.name)

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
    def chroot_denylist(self):
        """
        Parse the raw field 'chroot_denylist_raw' and return the list of
        wildcard patterns to match self.active_chroots against.
        """
        if not self.chroot_denylist_raw:
            return []

        denylisted = []
        for pattern in self.chroot_denylist_raw.split(','):
            pattern = pattern.strip()
            if not pattern:
                continue
            denylisted.append(pattern)

        return denylisted


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
        if not self.chroot_denylist_raw:
            return chroots

        filtered = [c for c in chroots if not self.matched_chroot(c, self.chroot_denylist)]
        # We never want to filter everything, this is a misconfiguration.
        return filtered if filtered else chroots


class Build(db.Model, helpers.Serializer):
    """
    Representation of one build in one copr
    """

    SCM_COMMIT = 'commit'
    SCM_PULL_REQUEST = 'pull-request'

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
    # directory name on backend with the source build results
    result_dir = db.Column(db.Text, default='', server_default='', nullable=False)
    # memory requirements for backend builder
    memory_reqs = db.Column(db.Integer, default=app.config["DEFAULT_BUILD_MEMORY"])
    # maximum allowed time of build, build will fail if exceeded
    timeout = db.Column(db.Integer, default=app.config["DEFAULT_BUILD_TIMEOUT"])
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

    source_status = db.Column(db.Integer, default=StatusEnum("waiting"),
                              nullable=False)
    srpm_url = db.Column(db.Text)

    isolation = db.Column(db.Text, default="default")

    bootstrap = db.Column(db.Text)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), index=True)
    user = db.relationship("User", backref=db.backref("builds"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), index=True)
    copr = db.relationship("Copr", backref=db.backref("builds"))
    package_id = db.Column(db.Integer, db.ForeignKey("package.id"), index=True)
    package = db.relationship("Package")

    chroots = association_proxy("build_chroots", "mock_chroot")

    batch_id = db.Column(db.Integer, db.ForeignKey("batch.id"), index=True)
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

    # used by webhook builds; e.g. github.com:praiskup, or pagure.io:jdoe
    submitted_by = db.Column(db.Text)

    # if a build was resubmitted from another build, this column will contain the original build id
    # the original build id is not here as a foreign key because the original build can be deleted so we can lost
    # the info that the build was resubmitted
    resubmitted_from_id = db.Column(db.Integer)

    __table_args__ = (
        db.Index('build_canceled', "canceled"),
        db.Index('build_order', "is_background", "id"),
        db.Index('build_filter', "source_type", "canceled"),
        db.Index('build_canceled_is_background_source_status_id_idx',
                 'canceled', "is_background", "source_status", "id"),
        db.Index('build_copr_id_package_id', "copr_id", "package_id"),
        db.Index("build_copr_id_build_id", "copr_id", "id", unique=True),
        db.Index("build_id_desc_per_copr_dir", id.desc(), "copr_dir_id"),
    )

    _cached_status = None
    _cached_status_set = None

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

    @property
    def get_source_log_urls(self):
        """
        Return a list of URLs to important build _source_ logs.  The list is
        changing as the state of build is changing.
        """
        logs = [self.source_live_log_url, self.source_backend_log_url,
                self.import_log_url_distgit]
        return list(filter(None, logs))

    @property
    def import_log_url_distgit(self):
        if self.source_state not in ["importing", "succeeded", "failed"]:
            return None

        days = app.config["HIDE_IMPORT_LOG_AFTER_DAYS"]
        if (time.time() - self.submitted_on) > days*24*3600:
            return None

        if app.config["COPR_DIST_GIT_LOGS_URL"]:
            return "{}/{}.log".format(app.config["COPR_DIST_GIT_LOGS_URL"],
                                      self.task_id.replace('/', '_'))
        return None

    @property
    def result_dir_url(self):
        """
        URL for the result-directory on backend (the source/SRPM build).
        """
        if not self.result_dir:
            return None
        parts = [
            "results", self.copr.owner_name, self.copr_dirname,
            # TODO: we should use self.result_dir instead of id_fixed_width
            "srpm-builds", self.id_fixed_width,
        ]
        path = os.path.normpath(os.path.join(*parts))
        return urljoin(app.config["BACKEND_BASE_URL"], path)

    def _compressed_log_variant(self, basename, states_raw_log):
        if not self.result_dir:
            return None
        if self.source_state in states_raw_log:
            return "/".join([self.result_dir_url, basename])
        if self.source_state in ["failed", "succeeded", "canceled",
                                 "importing"]:
            return "/".join([self.result_dir_url, basename + ".gz"])
        return None

    @property
    def source_live_log_url(self):
        """
        Full URL to the builder-live.log(.gz) for the source (SRPM) build.
        """
        return self._compressed_log_variant(
            "builder-live.log", ["running"]
        )

    @property
    def source_backend_log_url(self):
        """
        Full URL to the builder-live.log(.gz) for the source (SRPM) build.
        """
        return self._compressed_log_variant(
            "backend.log", ["starting", "running"]
        )

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
    def chroot_states(self):
        return list(map(lambda chroot: chroot.status, self.build_chroots))

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
    def source_state(self):
        """
        Return text representation of status of this build
        """
        if self.source_status is None:
            return "unknown"
        return StatusEnum(self.source_status)

    @property
    def status(self):
        """
        Return build status.
        """
        if self.canceled:
            return StatusEnum("canceled")

        use_src_states = ["starting", "pending", "running", "importing", "failed"]
        if self.source_state in use_src_states:
            return self.source_status

        if not self.chroot_states:
            # There were some builds in DB which had source_status equal
            # to 'succeeded', while they had no build_chroots created.
            # The original source of this inconsistency isn't known
            # because we only ever flip source_status to "succeded" directly
            # from the "importing" state.
            # Anyways, return something meaningful here so we can debug
            # properly if such situation happens.
            app.logger.error("Build %s has source_state %s, but "
                             "no build_chroots", self.id, self.source_state)
            return StatusEnum("waiting")

        for state in ["running", "starting", "pending", "failed", "succeeded", "skipped", "forked"]:
            if StatusEnum(state) in self.chroot_states:
                return StatusEnum(state)

        if StatusEnum("waiting") in self.chroot_states:
            # We should atomically flip
            # a) build.source_status: "importing" -> "succeeded" and
            # b) biuld_chroot.status: "waiting" -> "pending"
            # so at this point nothing really should be in "waiting" state.
            app.logger.error("Build chroots pending, even though build %s"
                             " has succeeded source_status", self.id)
            return StatusEnum("pending")

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
        return not self.finished

    @property
    def repeatable(self):
        """
        Find out if this build is repeatable.

        Build is repeatable only if sources has been imported.
        """
        return self.source_status == StatusEnum("succeeded")

    @property
    def finished_early(self):
        """
        Check if the build has finished, and if that happened prematurely
        because:
        - it was canceled
        - it failed to generate/download sources).
        That said, whether it's clear that the build has finished and we don't
        have to do additional SQL query to check corresponding BuildChroots.
        """
        if self.canceled:
            return True
        if self.source_status in [StatusEnum("failed"), StatusEnum("canceled")]:
            return True
        return False

    @property
    def finished(self):
        """
        Find out if this build is in finished state.

        Build is finished only if all its build_chroots are in finished state or
        the build was canceled.
        """
        if self.finished_early:
            return True
        if not self.build_chroots:
            return StatusEnum(self.source_status) in helpers.FINISHED_STATES
        return all([chroot.finished for chroot in self.build_chroots])

    @property
    def blocked(self):
        """
        Detect if the batch we are in is blocked.
        """
        return bool(self.batch and self.batch.blocked)

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

    @property
    def submitter(self):
        """
        Return tuple (submitter_string, submitter_link), while the
        submitter_link may be empty if we are not able to detect it
        wisely.
        """
        if self.user:
            user = self.user.name
            return (user, url_for('coprs_ns.coprs_by_user', username=user))

        if self.submitted_by:
            links = ['http://', 'https://']
            if any([self.submitted_by.startswith(x) for x in links]):
                return (self.submitted_by, self.submitted_by)

            return (self.submitted_by, None)

        return (None, None)

    @property
    def sandbox(self):
        """
        Return a string unique to project + submitter.  At this level copr
        backend later applies builder user-VM separation policy (VMs are only
        re-used for builds which have the same build.sandbox value)
        """
        submitter, _ = self.submitter
        if not submitter:
            # If we don't know build submitter, use "random" value and keep the
            # build separated from any other.
            submitter = uuid.uuid4()

        return '{0}--{1}'.format(self.copr.full_name, submitter)

    @property
    def resubmitted_from(self):
        return Build.query.filter(Build.id == self.resubmitted_from_id).first()

    @property
    def source_is_uploaded(self):
        return self.source_type == helpers.BuildSourceEnum('upload')

    @property
    def bootstrap_set(self):
        """ Is bootstrap config from project/chroot overwritten by build? """
        if not self.bootstrap:
            return False
        return self.bootstrap != "unchanged"

    @property
    def isolation_set(self):
        """ Is isolation config from project overwritten by build? """
        if not self.isolation:
            return False
        return self.isolation != "unchanged"

    def batching_user_error(self, user, modify=False):
        """
        Check if the USER can operate with this build in batches, eg create a
        new batch for it, or add other builds to the existing batch.  Return the
        error message (or None, if everything is OK).
        """
        # pylint: disable=too-many-return-statements
        if self.batch:
            if not modify:
                # Anyone can create a new batch which **depends on** an already
                # existing batch (even if it is owned by someone else)
                return None

            if self.batch.finished:
                return "Batch {} is already finished".format(self.batch.id)

            if self.batch.can_assign_builds(user):
                # user can modify an existing project...
                return None

            project_names = [c.full_name for c in self.batch.assigned_projects]
            projects = helpers.pluralize("project", project_names)
            return (
                "The batch {} belongs to {}.  You are not allowed to "
                "build there, so you neither can edit the batch."
            ).format(self.batch.id, projects)

        # a new batch is needed ...
        msgbase = "Build {} is not yet in any batch, and ".format(self.id)
        if not user.can_build_in(self.copr):
            return msgbase + (
                "user '{}' doesn't have the build permissions in project '{}' "
                "to create a new one"
            ).format(user.username, self.copr.full_name)

        if self.finished:
            return msgbase + (
                "new batch can not be created because the build has "
                "already finished"
            )

        return None  # new batch can be safely created

    @property
    def chroots_still_active(self):
        """
        Same as self.chroots, but the EOLed and disabled chroots are filtered
        out (IOW set of chroot we can safely resubmit this build against).
        """
        return [ch for ch in self.chroots if ch in self.copr.active_chroots]

    @property
    def results_dict(self):
        """
        Built packages in each build chroot.
        """
        return {bc.name: bc.results_dict for bc in self.build_chroots}

    @property
    def appstream(self):
        """Whether appstream metadata should be generated for a build."""
        return self.copr.appstream


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
        db.CheckConstraint("os_version not like '%-%'",
                           name="no_dash_in_version_check"),
    )

    id = db.Column(db.Integer, primary_key=True)
    # fedora/epel/..., mandatory
    os_release = db.Column(db.String(50), nullable=False)
    # 18/rawhide/..., can't contain '-' symbol, see tuple_from_name
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

    comment = db.Column(db.Text, nullable=True)

    multilib_pairs = {
        'x86_64': 'i386',
    }

    # A space separated list of tags.  Typically used as additional tags for the
    # Resalloc system to match appropriate builder.
    tags_raw = db.Column(db.String(50), nullable=True)

    @classmethod
    def latest_fedora_branched_chroot(cls, arch='x86_64'):
        return (cls.query
                .filter(cls.is_active == True)
                .filter(cls.os_release == 'fedora')
                .filter(cls.os_version != 'rawhide')
                .filter(cls.os_version != 'eln')
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

    @property
    def tags(self):
        """
        Return the list (of strings) of MockChroot tags.
        """
        return self.tags_raw.split() if self.tags_raw else []

    @property
    def os_family(self):
        """
        Returns family of OS.
        centos-stream -> centos
        opensuse-leap -> opensuse
        """
        return self.os_release.split("-")[0]


class CoprChroot(db.Model, helpers.Serializer):
    """
    Representation of Copr<->MockChroot M:N relation.

    This table basically determines what chroots are enabled in what projects.
    But it also contains configuration for assigned Copr/MockChroot pairs.

    We create/delete instances of this class when user enables/disables the
    chroots in his project.  That said, we don't keep history of changes here
    which means that there's only one configuration at any time.
    """

    id = db.Column('id', db.Integer, primary_key=True)

    __table_args__ = (
        # For now we don't allow adding multiple CoprChroots having the same
        # assigned MockChroot into the same project, but we could allow this
        # in future (e.g. two chroots for 'fedora-rawhide-x86_64', both with
        # slightly different configuration).
        db.UniqueConstraint("mock_chroot_id", "copr_id",
                            name="copr_chroot_mock_chroot_id_copr_id_uniq"),
    )

    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))

    buildroot_pkgs = db.Column(db.Text)
    repos = db.Column(db.Text, default="", server_default="", nullable=False)
    mock_chroot_id = db.Column(db.Integer, db.ForeignKey("mock_chroot.id"),
                               nullable=False)
    mock_chroot = db.relationship(
        "MockChroot", backref=db.backref("copr_chroots"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"), nullable=False,
                        index=True)
    copr = db.relationship("Copr",
                           backref=db.backref(
                               "copr_chroots",
                               single_parent=True,
                               cascade="all,delete,delete-orphan"))

    comps_zlib = db.Column(db.LargeBinary(), nullable=True)
    comps_name = db.Column(db.String(127), nullable=True)

    module_toggle = db.Column(db.Text, nullable=True)

    with_opts = db.Column(db.Text, default="", server_default="", nullable=False)
    without_opts = db.Column(db.Text, default="", server_default="", nullable=False)

    # Once mock_chroot gets EOL, copr_chroots are going to be deleted
    # if their admins don't extend their time span
    delete_after = db.Column(db.DateTime, index=True)
    # The last time when we successfully sent the notification e-mail about this
    # chroot, we'll not re-send before another EOL_CHROOTS_NOTIFICATION_PERIOD.
    delete_notify = db.Column(db.DateTime, index=True)

    bootstrap = db.Column(db.Text)
    bootstrap_image = db.Column(db.Text)

    isolation = db.Column(db.Text, default="unchanged")
    deleted = db.Column(db.Boolean, default=False, index=True)

    def update_comps(self, comps_xml):
        """
        save (compressed) the comps_xml file content (instance of bytes).
        """
        self.comps_zlib = zlib.compress(comps_xml)

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
    def name(self):
        return self.mock_chroot.name

    @property
    def full_name(self):
        """
        Return a full path for identifying some chroot, e.g.
        `@copr/copr-dev/fedora-rawhide-x86_64`
        """
        return "{0}/{1}".format(self.copr.full_name, self.name)

    @property
    def is_active(self):
        return self.mock_chroot.is_active

    @property
    def delete_status(self):
        """
        When a chroot is marked as EOL or when it is unclicked from a project,
        it goes through several stages before its data is finally deleted.
        The pipeline is:  active -> preserved -> expired -> deleted
        For detailed description of each state, see `ChrootDeletionStatus`.

        The WTF/minute ratio for reading this method is way above bearable level
        but we are considering 5 boolean variables and basically doing 2^5
        binary table.
        """
        # pylint: disable=too-many-return-statements

        # These are chroots, that were unclicked by user in project settings
        if self.deleted:
            if not self.delete_after:
                return ChrootDeletionStatus("deleted")

            if self.delete_after < datetime.datetime.now():
                return ChrootDeletionStatus("expired")

            return ChrootDeletionStatus("preserved")

        # Chroots that we deactivated or marked as EOL
        if not self.is_active:
            # This chroot is not EOL, its just _temporarily_ deactivated
            if not self.delete_after and not self.delete_notify:
                return ChrootDeletionStatus("deactivated")

            # We can never ever remove EOL chroots that we didn't send
            # a notification about
            if not self.delete_notify:
                return ChrootDeletionStatus("preserved")

            if not self.delete_after:
                return ChrootDeletionStatus("deleted")

            if self.delete_after < datetime.datetime.now():
                return ChrootDeletionStatus("expired")

            return ChrootDeletionStatus("preserved")

        if not self.delete_after and not self.delete_notify:
            return ChrootDeletionStatus("active")

        raise RuntimeError("Undefined status, this shouldn't happen")

    @property
    def delete_status_str(self):
        """
        A string version of `delete_status`
        """
        return ChrootDeletionStatus(self.delete_status)

    @property
    def delete_after_expired(self):
        """
        Is the chroot expired, aka its contents are going to be removed very
        soon, or already removed?  Using `delete_after_days` as a boolean is not
        sufficient because that would return wrong results for the last 24
        hours.
        """
        return self.delete_status in [ChrootDeletionStatus("expired"),
                                      ChrootDeletionStatus("deleted")]

    @property
    def delete_after_days(self):
        if not self.delete_after:
            return None
        now = datetime.datetime.now()
        days = (self.delete_after - now).days
        return days if days > 0 else 0

    @property
    def delete_after_humanized(self):
        """
        Return how soon the chroot is going to be deleted (expired).
        The largest unit we use is a day and the smallest is an hour. When the
        remaining time is just a couple of minutes or seconds, we just say that
        it is "less then an hour".
        """
        if self.delete_after is None:
            return None

        if self.delete_after_expired:
            return "To be removed in next cleanup"

        delta = self.delete_after - datetime.datetime.now()
        if delta.days:
            return "{0} days".format(delta.days)

        hours = int(round(delta.seconds / 3600))
        if hours:
            return "{0} hours".format(hours)
        return "less then an hour"

    @property
    def module_setup_commands(self):
        commands = []
        modules = self.module_toggle.split(",") if self.module_toggle else []
        for m in modules:
            m = m.strip()
            mod_tuple = {"disable": m[1:]} if m[0] == "!" else {"enable": m}
            commands.append(mod_tuple)
        return commands

    def to_dict(self):
        options = {"__columns_only__": [
            "buildroot_pkgs", "repos", "comps_name", "copr_id", "with_opts", "without_opts"
        ]}
        d = super(CoprChroot, self).to_dict(options=options)
        d["mock_chroot"] = self.mock_chroot.name
        return d

    @property
    def bootstrap_setup(self):
        """ Get Copr+CoprChroot consolidated bootstrap configuration """
        settings = {}
        settings['bootstrap'] = self.copr.bootstrap

        if self.bootstrap_changed:
            # overwrite project default with chroot config
            settings['bootstrap'] = self.bootstrap
            if settings['bootstrap'] == 'custom_image':
                settings['bootstrap_image'] = self.bootstrap_image
        if settings['bootstrap'] in [None, "default"]:
            return {}
        return settings

    @property
    def bootstrap_changed(self):
        """ True when chroot-specific bootstrap configuration specified """
        return self.bootstrap and self.bootstrap != 'unchanged'

    @property
    def isolation_setup(self):
        """ Is isolation config from project overwritten by chroot? """
        settings = {'isolation': self.copr.isolation}
        if self.isolation and self.isolation != 'unchanged':
            settings['isolation'] = self.isolation
        if settings['isolation'] in [None, "default"]:
            return {}
        return settings


class BuildChroot(db.Model, helpers.Serializer):
    """
    Representation of Build<->MockChroot relation
    """

    __table_args__ = (
        db.Index("build_chroot_status_started_on_idx", "status", "started_on"),
        db.UniqueConstraint("mock_chroot_id", "build_id",
                            name="build_chroot_mock_chroot_id_build_id_uniq"),
    )

    id = db.Column('id', db.Integer, primary_key=True)

    # The copr_chrot field needs to be nullable because we don't remove
    # BuildChroot when we delete CoprChroot.
    copr_chroot_id = db.Column(
        db.Integer,
        db.ForeignKey("copr_chroot.id", ondelete="SET NULL"),
        nullable=True, index=True,
    )
    copr_chroot = db.relationship("CoprChroot",
                                  backref=db.backref("build_chroots"))

    # The mock_chroot reference is not redundant!  We need it because reference
    # through copr_chroot.mock_chroot is disposable.
    mock_chroot_id = db.Column(db.Integer, db.ForeignKey("mock_chroot.id"),
                               nullable=False)
    mock_chroot = db.relationship("MockChroot", backref=db.backref("builds"))
    build_id = db.Column(db.Integer,
                         db.ForeignKey("build.id", ondelete="CASCADE"),
                         index=True, nullable=False)
    build = db.relationship("Build", backref=db.backref("build_chroots", cascade="all, delete-orphan",
                                                        passive_deletes=True))
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
        if self.build.finished_early:
            return True
        return self.state in helpers.FINISHED_STATES

    @property
    def task_id(self):
        return "{}-{}".format(self.build_id, self.name)

    @property
    def dist_git_url(self):
        if app.config["DIST_GIT_URL"]:
            if self.state == "forked":
                if self.build.copr.forked_from.deleted:
                    return None
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

    def _compressed_log_variant(self, basename, states_raw_log):
        if not self.result_dir:
            return None
        if not self.build.package:
            # no source build done, yet
            return None
        if self.state in states_raw_log:
            return os.path.join(self.result_dir_url,
                                basename)
        if self.state in ["failed", "succeeded", "canceled", "importing"]:
            return os.path.join(self.result_dir_url,
                                basename + ".gz")
        return None

    @property
    def rpm_live_log_url(self):
        """ Full URL to the builder-live.log.gz for RPM build.  """
        return self._compressed_log_variant("builder-live.log", ["running"])

    @property
    def rpm_backend_log_url(self):
        """ Link to backend.log[.gz] related to RPM build.  """
        return self._compressed_log_variant("backend.log",
                                            ["starting", "running"])

    @property
    def fedora_review(self):
        """ Whether the project is intended for fedora review. """
        if not self.build.source_json:
            return False
        if "fedora_review" in self.build.source_json and self.mock_chroot.name.startswith("fedora-"):
            return True
        return False

    @property
    def rpm_fedora_review_url(self):
        """
        Full URL to the review.txt file produced by the `fedora-review` tool. If
        the `fedora-review` tool is not enabled for this project, return `None`.

        At this moment, the `review.txt` file (and the rest of the
        `fedora-review` output) is uncompressed for all states.
        """
        if not self.fedora_review:
            return None
        return self._compressed_log_variant("fedora-review/review.txt",
                                            StatusEnum.vals.keys())

    @property
    def rpm_live_logs(self):
        """ return list of live log URLs """
        logs = []
        log = self.rpm_backend_log_url
        if log:
            logs.append(log)

        log = self.rpm_live_log_url
        if log:
            logs.append(log)

        log = self.rpm_fedora_review_url
        if log and self.finished:
            logs.append(log)
        return logs

    @property
    def results_dict(self):
        """
        Returns a `dict` containing all built packages in this chroot
        """
        built_packages = []
        for result in self.results:
            options = {"__columns_except__": ["id", "build_chroot_id"]}
            result_dict= result.to_dict(options=options)
            built_packages.append(result_dict)
        return {"packages": built_packages}

    @property
    def distgit_clone_url(self):
        """
        Return a CoprDir specific DistGit clone URL.  We can not just use
        self.build.package.dist_git_clone_url because that one is not
        CoprDir-specific.
        """
        dirname = self.build.copr_dir.full_name
        package = self.build.package.name
        return "{}/{}/{}".format(app.config["DIST_GIT_CLONE_URL"], dirname, package)


class BuildChrootResult(db.Model, helpers.Serializer):
    """
    Represents a built package within some `BuildChroot`
    """

    id = db.Column(db.Integer, primary_key=True)
    build_chroot_id = db.Column(
        db.Integer,
        db.ForeignKey("build_chroot.id"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.Text, nullable=False)
    epoch = db.Column(db.Integer, default=0)
    version = db.Column(db.Text, nullable=False)
    release = db.Column(db.Text, nullable=False)
    arch = db.Column(db.Text, nullable=False)

    build_chroot = db.relationship(
        "BuildChroot",
        backref=db.backref("results", cascade="all, delete-orphan"),
    )


class LegalFlag(db.Model, helpers.Serializer):
    id = db.Column(db.Integer, primary_key=True)
    # message from user who raised the flag (what he thinks is wrong)
    raise_message = db.Column(db.Text)
    # time of raising the flag as returned by int(time.time())
    raised_on = db.Column(db.Integer)
    # time of resolving the flag by admin as returned by int(time.time())
    resolved_on = db.Column(db.Integer, index=True)

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

    __table_args__ = (
        db.Index('action_result_action_type', 'result', 'action_type'),
    )

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
    # the higher the 'priority' is, the later the task is taken.
    # Keep actions priority in range -100 to 100
    priority = db.Column(db.Integer, nullable=True, default=0)
    # additional data
    data = db.Column(db.Text)
    # result of the action, see BackendResultEnum
    result = db.Column(
        db.Integer, default=BackendResultEnum("waiting"))
    # optional message from the backend/whatever
    message = db.Column(db.Text)
    # time created as returned by int(time.time())
    created_on = db.Column(db.Integer, index=True)
    # time ended as returned by int(time.time())
    ended_on = db.Column(db.Integer, index=True)

    def __str__(self):
        return self.__unicode__()

    def __unicode__(self):
        if self.action_type == ActionTypeEnum("delete"):
            return "Deleting {0} {1}".format(self.object_type, self.old_value)
        elif self.action_type == ActionTypeEnum("legal-flag"):
            return "Legal flag on copr {0}.".format(self.old_value)

        return "Action {0} on {1}, old value: {2}, new value: {3}.".format(
            self.action_type, self.object_type, self.old_value, self.new_value)

    def to_dict(self, options=None):
        d = super(Action, self).to_dict(options)
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

    @property
    def default_priority(self):
        action_type_str = ActionTypeEnum(self.action_type)
        return DefaultActionPriorityEnum.vals.get(action_type_str, 0)


class CounterStat(db.Model, helpers.Serializer):
    """
    Generic store for simple statistics.
    """

    name = db.Column(db.Text, primary_key=True)
    counter_type = db.Column(db.String(30))

    counter = db.Column(db.Integer, default=0, server_default="0")

    @property
    def pretty_name(self):
        """
        Return owner/project, or owner/project/chroot value
        """

        # TODO Once we add relationships to Copr and CoprChroot, use them here
        suffix = self.name.rsplit("::", 1)[-1]
        owner, project = suffix.rsplit("@", 1)

        # Chrootname after colon the separator
        if ":" in project:
            project = project.replace(":", "/")

        return "{0}/{1}".format(owner, project)


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
    blocked_by_id = db.Column(db.Integer, db.ForeignKey("batch.id"), nullable=True)
    blocked_by = db.relationship("Batch", remote_side=[id])

    _is_finished = None

    @property
    def finished_slow(self):
        """
        Check if this batch is finished by iterating through all the contained
        builds.
        """
        cache_timeout = 3600
        redis_cache_id = "batch_finished_{}".format(self.id)

        if app.cache.get(redis_cache_id):
            # prolong the cache after the access
            app.cache.set(redis_cache_id, True, timeout=cache_timeout)
            return True

        if not self.builds:
            # no builds assigned to this batch (yet)
            return False

        # Some Batches are rather large;  use the all+map pair here, not a list
        # comprehension, to escape the loop as soon as possible on the first
        # miss (comprehension would go through all builds unnecessarily)
        if all(map(lambda x: x.finished, self.builds)):
            # nothing can switch finished batch to non-finished state, cache it
            app.cache.set(redis_cache_id, True, cache_timeout)
            return True
        return False

    @property
    def finished(self):
        """
        Same as self.finished_slow, but doesn't require re-calculation for all
        the builds, buildchroots, states, etc.  Or checking Redis caches.
        """
        if self._is_finished is None:
            self._is_finished = self.finished_slow
        return self._is_finished

    @property
    def blocked(self):
        """
        Batch is blocked when the parent batch is not yet finished.
        """
        if not self.blocked_by_id:
            return False

        # a) we are blocked if parent is blocked, or ...
        if self.blocked_by.blocked:
            # Optimization, checking for "blocked" is often cheaper than
            # checking for "finished" because batches tend to contain too many
            # builds (and transitively build_chroots).  IOW, since in each batch
            # tree is only one batch being processed - it doesn't make sense to
            # re-calculate 'finished' state for all of them.
            return True

        # b) ... when parent is not yet finished
        return not self.blocked_by.finished

    @property
    def state(self):
        if self.blocked:
            return "blocked"
        return "finished" if self.finished else "processing"

    @property
    def assigned_projects(self):
        """ Get a list (generator) of assigned projects """
        seen = set()
        for build in self.builds:
            copr = build.copr
            if copr in seen:
                continue
            seen.add(copr)
            yield copr

    def can_assign_builds(self, user):
        """
        Check if USER has permissions to assign builds to this batch.  Since we
        support cross-project batches, user is allowed to add a build to this
        batch as long as:
        - the batch has no builds yet (user has created a new batch now)
        - the batch has at least one build which belongs to project where the
          user has build access
        """
        if not self.builds:
            return True
        for copr in self.assigned_projects:
            if user.can_build_in(copr):
                return True
        return False

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
        # We would like to not access private member here
        return modulemd_tools.yaml._yaml2stream(self.yaml.decode("utf-8"))

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
        if self.action:
            return { BackendResultEnum("success"): ModuleStatusEnum("succeeded"),
                     BackendResultEnum("failure"): ModuleStatusEnum("failed"),
                     BackendResultEnum("waiting"): ModuleStatusEnum("waiting"),
                   }[self.action.result]
        build_statuses = [b.status for b in self.builds]
        for state in ["canceled", "running", "starting", "pending", "failed", "succeeded"]:
            if ModuleStatusEnum(state) in build_statuses:
                return ModuleStatusEnum(state)
        return ModuleStatusEnum("unknown")

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
        return {name: self.modulemd.get_profile(name).get_rpms()
                for name in self.modulemd.get_profile_names()}
    @property
    def components(self):
        return {name: self.modulemd.get_rpm_component(name)
                for name in self.modulemd.get_rpm_component_names()}


class BuildsStatistics(db.Model):
    time = db.Column(db.Integer, primary_key=True)
    stat_type = db.Column(db.Text, primary_key=True)
    running = db.Column(db.Integer)
    pending = db.Column(db.Integer)

class ActionsStatistics(db.Model):
    time = db.Column(db.Integer, primary_key=True)
    stat_type = db.Column(db.Text, primary_key=True)
    waiting = db.Column(db.Integer)
    success = db.Column(db.Integer)
    failed = db.Column(db.Integer)


class DistGitInstance(db.Model):
    """ Dist-git instances, e.g. Fedora/CentOS/RHEL/ """

    # numeric id, not used ATM
    id = db.Column(db.Integer, primary_key=True)

    # case sensitive identificator, e.g. 'fedora'
    name = db.Column(db.String(50), nullable=False, unique=True)

    # e.g. 'https://src.fedoraproject.org'
    clone_url = db.Column(db.String(100), nullable=False)

    # e.g. 'rpms/{pkgname}', needs to contain {pkgname} to be expanded later,
    # may contain '{namespace}'.
    clone_package_uri = db.Column(db.String(100), nullable=False)

    # for UI form ordering, higher number means higher priority
    priority = db.Column(db.Integer, default=100, nullable=False)

    # Some DistGit instances may support namespaces but doesn't require them.
    # e.g. Fedora DistGit which uses 'forks/user1' for forks but doesn't have
    # any namespace for main package repositories.
    #
    # There is a notable difference between empty string and None value.
    # None means, there is no default namespace defined and therefore if
    # `clone_package_uri` contains `{namespace}`, it needs to be specified by
    # the user. OTOH when empty string is used, it it passed as `{namespace}`
    # and therefore it doesn't have to be set by user.
    default_namespace = db.Column(db.String(50), nullable=True)

    def package_clone_url(self, pkgname, namespace=None):
        """
        Get the right git clone url for the package hosted in this dist git
        instance.
        """
        try:
            params = {"pkgname": pkgname}
            namespace = namespace or self.default_namespace
            if namespace is not None:
                params["namespace"] = namespace

            uri = self.clone_package_uri.format(**params)
            uri = os.path.normpath(uri).strip("/")
            return "/".join([self.clone_url, uri])
        except KeyError as k:
            raise KeyError("DistGit '{}' requires {} specified".format(
                self.name, k
            ))


class CancelRequest(db.Model):
    """ Requests for backend to cancel some background job """
    # for now we only cancel builds, so we have here task_id (either <build_id>
    # for SRPM builds, or <build_id>-<chroot> for RPM builds).
    what = db.Column(db.String(100), nullable=False, primary_key=True)


class ReviewedOutdatedChroot(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
        index=True,
    )
    copr_chroot_id = db.Column(
        db.Integer,
        db.ForeignKey("copr_chroot.id", ondelete="CASCADE"),
        nullable=False,
    )

    user = db.relationship(
        "User",
        backref=db.backref("reviewed_outdated_chroots"),
    )
    copr_chroot = db.relationship(
        "CoprChroot",
        backref=db.backref("reviewed_outdated_chroots",
                           cascade="all, delete-orphan")
    )


@listens_for(DistGitInstance.__table__, 'after_create')
def insert_fedora_distgit(*args, **kwargs):
    db.session.add(DistGitInstance(
        name="fedora",
        clone_url="https://src.fedoraproject.org",
        clone_package_uri="{namespace}/rpms/{pkgname}",
        default_namespace="",
    ))
