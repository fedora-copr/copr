import copy
import datetime
import json
import os
import flask

from sqlalchemy.ext.associationproxy import association_proxy
from libravatar import libravatar_url
import zlib

from coprs import constants
from coprs import db
from coprs import helpers
from coprs import app

import itertools
import operator
from coprs.helpers import BuildSourceEnum, StatusEnum, ActionTypeEnum, JSONEncodedDict


class User(db.Model, helpers.Serializer):

    """
    Represents user of the copr frontend
    """

    # PK;  TODO: the 'username' could be also PK
    id = db.Column(db.Integer, primary_key=True)

    # unique username
    username = db.Column(db.String(100), nullable=False, unique=True)

    # email
    mail = db.Column(db.String(150), nullable=False)

    # optional timezone
    timezone = db.Column(db.String(50), nullable=True)

    # is this user proven? proven users can modify builder memory and
    # timeout for single builds
    proven = db.Column(db.Boolean, default=False)

    # is this user admin of the system?
    admin = db.Column(db.Boolean, default=False)

    # stuff for the cli interface
    api_login = db.Column(db.String(40), nullable=False, default="abc")
    api_token = db.Column(db.String(40), nullable=False, default="abc")
    api_token_expiration = db.Column(
        db.Date, nullable=False, default=datetime.date(2000, 1, 1))

    # list of groups as retrieved from openid
    openid_groups = db.Column(JSONEncodedDict)

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
        if copr.owner_id == self.id:
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

        if copr.owner == self or self.admin:
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

        return (Copr.query.filter_by(owner=self).
                filter_by(deleted=False).
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


class Copr(db.Model, helpers.Serializer):

    """
    Represents a single copr (private repo with builds, mock chroots, etc.).
    """

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
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    owner = db.relationship("User", backref=db.backref("coprs"))
    group_id = db.Column(db.Integer, db.ForeignKey("group.id"))
    group = db.relationship("Group", backref=db.backref("groups"))
    mock_chroots = association_proxy("copr_chroots", "mock_chroot")

    # enable networking for the builds by default
    build_enable_net = db.Column(db.Boolean, default=True,
                                 server_default="1", nullable=False)

    __mapper_args__ = {
        "order_by": created_on.desc()
    }

    @property
    def is_a_group_project(self):
        return self.group_id is not None

    @property
    def owner_name(self):
        return self.owner.name

    @property
    def group_name(self):
        return self.group.name

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
    def modified_chroots(self):
        """
        Return list of chroots which has been modified
        """
        modified_chroots = []
        for chroot in self.copr_chroots:
            if chroot.buildroot_pkgs and chroot.is_active:
                modified_chroots.append(chroot)
        return modified_chroots

    def is_release_arch_modified(self, name_release, arch):
        if "{}-{}".format(name_release, arch) in \
                [chroot.name for chroot in self.modified_chroots]:
            return True
        return False

    @property
    def full_name(self):
        if self.is_a_group_project:
            return "@{}/{}".format(self.group.name, self.name)
        else:
            return "{}/{}".format(self.owner.username, self.name)

    @property
    def repo_name(self):
        if self.is_a_group_project:
            return "@{}-{}".format(self.group.name, self.name)
        else:
            return "{}-{}".format(self.owner.username, self.name)

    def to_dict(self, private=False, show_builds=True, show_chroots=True):
        result = {}
        for key in ["id", "name", "description", "instructions"]:
            result[key] = str(copy.copy(getattr(self, key)))
        result["owner"] = self.owner.name
        return result


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


class Package(db.Model, helpers.Serializer):
    """
    Represents a single package in a project.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    # Source of the build: type identifier
    source_type = db.Column(db.Integer, default=helpers.BuildSourceEnum("unset"))
    # Source of the build: description in json, example: git link, srpm url, etc.
    source_json = db.Column(db.Text)

    # relations
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))
    copr = db.relationship("Copr", backref=db.backref("packages"))

    @property
    def dist_git_repo(self):
        if self.copr.is_a_group_project:
            return "@{}/{}/{}".format(self.copr.group.name,
                                      self.copr.name,
                                      self.name)
        else:
            return "{}/{}/{}".format(self.copr.owner.name,
                                     self.copr.name,
                                     self.name)

    @property
    def source_json_dict(self):
        return json.loads(self.source_json)

    @property
    def source_type_text(self):
        return helpers.BuildSourceEnum(self.source_type)

    @property
    def dist_git_url(self):
        if app.config["DIST_GIT_URL"]:
            return "{}/{}.git".format(app.config["DIST_GIT_URL"], self.dist_git_repo)
        return None


class Build(db.Model, helpers.Serializer):

    """
    Representation of one build in one copr
    """

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
    # obsolete, see started_on property of each build_chroot
    started_on = db.Column(db.Integer)
    # means that ALL chroots are finished
    ended_on = db.Column(db.Integer)
    # url of the build results
    results = db.Column(db.Text)
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
    fail_type = db.Column(db.Integer, default=helpers.FailTypeEnum("unset"))

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref=db.backref("builds"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))
    copr = db.relationship("Copr", backref=db.backref("builds"))
    package_id = db.Column(db.Integer, db.ForeignKey("package.id"))
    package = db.relationship("Package", backref=db.backref("builds"))

    chroots = association_proxy("build_chroots", "mock_chroot")

    @property
    def user_name(self):
        return self.user.name

    @property
    def fail_type_text(self):
        return helpers.FailTypeEnum(self.fail_type)

    @property
    def is_older_results_naming_used(self):
        # we have changed result directory naming together with transition to dist-git
        # that's why we use so strange criterion
        return self.build_chroots[0].git_hash is None

    @property
    def repos_list(self):
        if self.repos is None:
            return list()
        else:
            return self.repos.split()

    @property
    def result_dir_name(self):
        return "{:08d}-{}".format(self.id, self.package.name)

    @property
    def source_json_dict(self):
        return json.loads(self.source_json)

    @property
    def min_started_on(self):
        mb_list = [chroot.started_on for chroot in
                   self.build_chroots if chroot.started_on]
        if len(mb_list) > 0:
            return min(mb_list)
        else:
            return None

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
    def has_pending_chroot(self):
        # FIXME bad name
        # used when checking if the repo is initialized and results can be set
        # i think this is the only purpose - check
        return StatusEnum("pending") in self.chroot_states or \
            StatusEnum("starting") in self.chroot_states

    @property
    def has_unfinished_chroot(self):
        return StatusEnum("pending") in self.chroot_states or \
            StatusEnum("starting") in self.chroot_states or \
            StatusEnum("running") in self.chroot_states

    @property
    def has_importing_chroot(self):
        return StatusEnum("importing") in self.chroot_states

    @property
    def status(self):
        """
        Return build status according to build status of its chroots
        """
        if self.canceled:
            return StatusEnum("canceled")

        for state in ["failed", "running", "starting", "importing", "pending", "succeeded", "skipped"]:
            if StatusEnum(state) in self.chroot_states:
                return StatusEnum(state)

    @property
    def state(self):
        """
        Return text representation of status of this build
        """

        if self.status is not None:
            return StatusEnum(self.status)

        return "unknown"

    @property
    def cancelable(self):
        """
        Find out if this build is cancelable.

        Build is cancelabel only when it's pending (not started)
        """

        return self.status == StatusEnum("pending") or \
            self.status == StatusEnum("importing")

    @property
    def repeatable(self):
        """
        Find out if this build is repeatable.

        Build is repeatable only if it's not pending, starting or running
        """
        return self.status not in [StatusEnum("pending"),
                                   StatusEnum("starting"),
                                   StatusEnum("running"), ]

    @property
    def deletable(self):
        """
        Find out if this build is deletable.

        Build is deletable only when it's finished. (also means cancelled)
        It is important to remember that "failed" state doesn't ultimately
        mean it's finished - so we need to check whether the "ended_on"
        property has been set.
        """

        # build failed due to import error
        if self.state == "failed" and self.started_on is None:
            return True

        # build failed and all chroots are finished
        if self.state == "failed" and self.ended_on is not None:
            return True

        return self.state in ["succeeded", "canceled", "skipped"]

    @property
    def src_pkg_name(self):
        """
        Extract source package name from source name or url
        todo: obsolete
        """
        src_rpm_name = self.pkgs.split("/")[-1]
        if src_rpm_name.endswith(".src.rpm"):
            return src_rpm_name[:-8]
        else:
            return src_rpm_name

    @property
    def package_name(self):
        try:
            return self.package.name
        except:
            return None

    def to_dict(self, options=None):
        result = super(Build, self).to_dict(options)
        result["src_pkg"] = result["pkgs"]
        del result["pkgs"]
        del result["copr_id"]

        result["state"] = self.state
        return result


class MockChroot(db.Model, helpers.Serializer):

    """
    Representation of mock chroot
    """

    id = db.Column(db.Integer, primary_key=True)
    # fedora/epel/..., mandatory
    os_release = db.Column(db.String(50), nullable=False)
    # 18/rawhide/..., optional (mock chroot doesn"t need to have this)
    os_version = db.Column(db.String(50), nullable=False)
    # x86_64/i686/..., mandatory
    arch = db.Column(db.String(50), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

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
    def name_release_human(self):
        """
        Textual representation of name of this or release
        """
        return "{} {}".format(self.os_release, self.os_version)

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

    def update_comps(self, comps_xml):
        self.comps_zlib = zlib.compress(comps_xml.encode("utf-8"))

    @property
    def buildroot_pkgs_list(self):
        return self.buildroot_pkgs.split()

    @property
    def comps(self):
        if self.comps_zlib:
            return zlib.decompress(self.comps_zlib).decode("utf-8")

    @property
    def comps_len(self):
        if self.comps_zlib:
            return len(zlib.decompress(self.comps_zlib))
        else:
            return 0

    @property
    def name(self):
        return self.mock_chroot.name

    @property
    def is_active(self):
        return self.mock_chroot.is_active


class BuildChroot(db.Model, helpers.Serializer):

    """
    Representation of Build<->MockChroot relation
    """

    mock_chroot_id = db.Column(db.Integer, db.ForeignKey("mock_chroot.id"),
                               primary_key=True)
    mock_chroot = db.relationship("MockChroot", backref=db.backref("builds"))
    build_id = db.Column(db.Integer, db.ForeignKey("build.id"),
                         primary_key=True)
    build = db.relationship("Build", backref=db.backref("build_chroots"))
    git_hash = db.Column(db.String(40))
    status = db.Column(db.Integer, default=StatusEnum("importing"))

    started_on = db.Column(db.Integer)
    ended_on = db.Column(db.Integer)

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
    def dist_git_url(self):
        if app.config["DIST_GIT_URL"]:
            return "{}/{}.git/commit/?id={}".format(app.config["DIST_GIT_URL"],
                                                    self.build.package.dist_git_repo,
                                                    self.git_hash)
        return None

    @property
    def result_dir_url(self):
        return "/".join([app.config["BACKEND_BASE_URL"],
                         u"results",
                         self.result_dir])

    @property
    def result_dir(self):
        # hide changes occurred after migration to dist-git
        # if build has defined dist-git, it means that new schema should be used
        # otherwise use older structure

        # old: results/valtri/ruby/fedora-rawhide-x86_64/rubygem-aws-sdk-resources-2.1.11-1.fc24/
        # new: results/asamalik/rh-perl520/epel-7-x86_64/00000187-rh-perl520/

        parts = []
        if self.build.copr.is_a_group_project:
            parts.append(u"@{}".format(self.build.copr.group.name))
        else:
            parts.append(self.build.copr.owner.username)

        parts.extend([
            self.build.copr.name,
            self.name,
        ])
        if self.git_hash is not None and self.build.package:
            parts.append(self.build.result_dir_name)
        else:
            parts.append(self.build.src_pkg_name)

        return os.path.join(*parts)

    def __str__(self):
        return "<BuildChroot: {}>".format(self.to_dict())


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
    # delete, rename, ...; see ActionTypeEnum
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
    # result of the action, see helpers.BackendResultEnum
    result = db.Column(
        db.Integer, default=helpers.BackendResultEnum("waiting"))
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
        elif self.action_type == ActionTypeEnum("rename"):
            return "Renaming {0} from {1} to {2}.".format(self.object_type,
                                                          self.old_value,
                                                          self.new_value)
        elif self.action_type == ActionTypeEnum("legal-flag"):
            return "Legal flag on copr {0}.".format(self.old_value)

        return "Action {0} on {1}, old value: {2}, new value: {3}.".format(
            self.action_type, self.object_type, self.old_value, self.new_value)


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
