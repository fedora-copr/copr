import datetime

from sqlalchemy.ext.associationproxy import association_proxy
from libravatar import libravatar_url

from coprs import constants
from coprs import db
from coprs import helpers


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

        return can_build

    def can_edit(self, copr):
        """
        Determine if this user can edit the given copr.
        """

        can_edit = False
        if copr.owner == self:
            can_edit = True
        if (self.permissions_for_copr(copr) and
                self.permissions_for_copr(copr).copr_admin ==
                helpers.PermissionEnum("approved")):

            can_edit = True

        return can_edit

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
    mock_chroots = association_proxy("copr_chroots", "mock_chroot")

    # enable networking for the builds by default
    build_enable_net = db.Column(db.Boolean, default=True,
                                 server_default="1", nullable=False)

    __mapper_args__ = {
        "order_by": created_on.desc()
    }

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

    def check_copr_chroot(self, chroot):
        """
        Return object of chroot, if is related to our copr or None

        :type chroot: CoprChroot
        """

        result = None
        # there will be max ~10 chroots per build, iteration will be probably
        # faster than sql query
        for copr_chroot in self.copr_chroots:
            if copr_chroot.mock_chroot_id == chroot.id:
                result = copr_chroot
                break
        return result

    def buildroot_pkgs(self, chroot):
        """
        Return packages in minimal buildroot for given chroot.
        """

        result = ""
        # this is ugly as user can remove chroot after he submit build, but
        # lets call this feature
        copr_chroot = self.check_copr_chroot(chroot)
        if copr_chroot:
            result = copr_chroot.buildroot_pkgs
        return result

    @property
    def modified_chroots(self):
        """
        Return list of chroots which has been modified
        """
        modified_chroots = []
        for chroot in self.active_chroots:
            if self.buildroot_pkgs(chroot):
                modified_chroots.append(chroot)
        return modified_chroots

    def is_release_arch_modified(self, name_release, arch):
        if "{}-{}".format(name_release, arch) in [chroot.name for chroot in self.modified_chroots]:
            return True
        return False

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
    source_type = db.Column(db.Integer, default=helpers.BuildSourceEnum("srpm_link"))
    # Source of the build: description in json, example: git link, srpm url, etc.
    source_json = db.Column(db.Text)

    # relations
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))
    copr = db.relationship("Copr", backref=db.backref("packages"))

    @property
    def gist_git_repo(self):
        pass


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
    source_type = db.Column(db.Integer, default=helpers.BuildSourceEnum("srpm_link"))
    # Source of the build: description in json, example: git link, srpm url, etc.
    source_json = db.Column(db.Text)

    # relations
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    user = db.relationship("User", backref=db.backref("builds"))
    copr_id = db.Column(db.Integer, db.ForeignKey("copr.id"))
    copr = db.relationship("Copr", backref=db.backref("builds"))
    package_id = db.Column(db.Integer, db.ForeignKey("package.id"))
    package = db.relationship("Package", backref=db.backref("builds"))

    chroots = association_proxy("build_chroots", "mock_chroot")

    @property
    def min_started_on(self):
        return min(chroot.started_on for chroot in
                   self.build_chroots if chroot.started_on)

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
        return helpers.StatusEnum("pending") in self.chroot_states or \
            helpers.StatusEnum("starting") in self.chroot_states

    @property
    def has_unfinished_chroot(self):
        return helpers.StatusEnum("pending") in self.chroot_states or \
            helpers.StatusEnum("starting") in self.chroot_states or \
            helpers.StatusEnum("running") in self.chroot_states

    @property
    def status(self):
        """
        Return build status according to build status of its chroots
        """

        if self.canceled:
            return helpers.StatusEnum("canceled")

        for state in ["failed", "running", "starting", "uploading", "pending", "succeeded", "skipped"]:
            if helpers.StatusEnum(state) in self.chroot_states:
                return helpers.StatusEnum(state)

    @property
    def state(self):
        """
        Return text representation of status of this build
        """

        if self.status is not None:
            return helpers.StatusEnum(self.status)

        return "unknown"

    @property
    def cancelable(self):
        """
        Find out if this build is cancelable.

        Build is cancelabel only when it's pending (not started)
        """

        return self.status == helpers.StatusEnum("pending")

    @property
    def repeatable(self):
        """
        Find out if this build is repeatable.

        Build is repeatable only if it's not pending, starting or running
        """

        return self.status not in [helpers.StatusEnum("pending"),
                                   helpers.StatusEnum("starting"),
                                   helpers.StatusEnum("running"), ]

    @property
    def deletable(self):
        """
        Find out if this build is deletable.

        Build is deletable only when it's finished. (also means cancelled)
        It is important to remember that "failed" state doesn't ultimately
        mean it's finished - so we need to check whether the "ended_on"
        property has been set.
        """

        if self.state == "failed" and self.ended_on is not None:
            return True

        return self.state in ["succeeded", "canceled", "skipped"]

    @property
    def src_pkg_name(self):
        """
        Extract source package name from URL
        """
        src_rpm_name = self.pkgs.split("/")[-1]
        if src_rpm_name.endswith(".src.rpm"):
            return src_rpm_name[:-8]
        else:
            return src_rpm_name


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
        return "{0}-{1}-{2}".format(self.os_release, self.os_version, self.arch)

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
    status = db.Column(db.Integer, default=helpers.StatusEnum("pending"))
    git_hash = db.Column(db.String(40))

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
            return helpers.StatusEnum(self.status)

        return "unknown"

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
    # delete, rename, ...; see helpers.ActionTypeEnum
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
        if self.action_type == helpers.ActionTypeEnum("delete"):
            return "Deleting {0} {1}".format(self.object_type, self.old_value)
        elif self.action_type == helpers.ActionTypeEnum("rename"):
            return "Renaming {0} from {1} to {2}.".format(self.object_type,
                                                          self.old_value,
                                                          self.new_value)
        elif self.action_type == helpers.ActionTypeEnum("legal-flag"):
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

