import re
from six.moves.urllib.parse import urlparse

import flask
import wtforms
import json

from flask_wtf.file import FileRequired, FileField
from fnmatch import fnmatch

try: # get rid of deprecation warning with newer flask_wtf
    from flask_wtf import FlaskForm
except ImportError:
    from flask_wtf import Form as FlaskForm

from coprs import constants
from coprs import app
from coprs import helpers
from coprs import models
from coprs.logic.coprs_logic import CoprsLogic, MockChrootsLogic
from coprs.logic.users_logic import UsersLogic
from coprs import exceptions


FALSE_VALUES = {False, "false", ""}


def get_package_form_cls_by_source_type_text(source_type_text):
    """
    Params
    ------
    source_type_text : str
        name of the source type (scm/pypi/rubygems/git_and_tito/mock_scm)

    Returns
    -------
    BasePackageForm child
        based on source_type_text input
    """
    if source_type_text == 'scm':
        return PackageFormScm
    elif source_type_text == 'pypi':
        return PackageFormPyPI
    elif source_type_text == 'rubygems':
        return PackageFormRubyGems
    elif source_type_text == 'git_and_tito':
        return PackageFormTito # deprecated
    elif source_type_text == 'mock_scm':
        return PackageFormMock # deprecated
    elif source_type_text == "custom":
        return PackageFormCustom
    else:
        raise exceptions.UnknownSourceTypeException("Invalid source type")


class MultiCheckboxField(wtforms.SelectMultipleField):
    widget = wtforms.widgets.ListWidget(prefix_label=False)
    option_widget = wtforms.widgets.CheckboxInput()


class UrlListValidator(object):

    def __init__(self, message=None):
        if not message:
            message = ("A list of http[s] URLs separated by whitespace characters"
                       " is needed ('{0}' doesn't seem to be a valid URL).")
        self.message = message

    def __call__(self, form, field):
        urls = field.data.split()
        for u in urls:
            if not self.is_url(u):
                raise wtforms.ValidationError(self.message.format(u))

    def is_url(self, url):
        parsed = urlparse(url)
        if not parsed.scheme.startswith("http"):
            return False
        if not parsed.netloc:
            return False
        return True


class UrlRepoListValidator(UrlListValidator):
    """ Allows also `repo://` schema"""
    def is_url(self, url):
        parsed = urlparse(url)
        if parsed.scheme not in ["http", "https", "copr"]:
            return False
        if not parsed.netloc:
            return False
        #  copr://username/projectname
        #  ^^ schema ^^ netlock  ^^ path
        if parsed.scheme == "copr":
            # check if projectname missed
            path_split = parsed.path.split("/")
            if len(path_split) < 2 or path_split[1] == "":
                return False

        return True


class UrlSrpmListValidator(UrlListValidator):
    def __init__(self, message=None):
        if not message:
            message = ("URLs must end with .src.rpm, .nosrc.rpm, or .spec"
                       " ('{0}' doesn't seem to be a valid URL).")
        super(UrlSrpmListValidator, self).__init__(message)

    def is_url(self, url):
        parsed = urlparse(url)
        if not parsed.path.endswith((".src.rpm", ".nosrc.rpm", ".spec")):
            return False
        return True


class SrpmValidator(object):
    def __init__(self, message=None):
        if not message:
            message = "You can upload only .src.rpm, .nosrc.rpm, and .spec files"
        self.message = message

    def __call__(self, form, field):
        filename = field.data.filename.lower()
        if not filename.endswith((".src.rpm", ".nosrc.rpm", ".spec")):
            raise wtforms.ValidationError(self.message)


class CoprUniqueNameValidator(object):

    def __init__(self, message=None, user=None, group=None):
        if not message:
            if group is None:
                message = "You already have project named '{}'."
            else:
                message = "Group {} ".format(group) + "already have project named '{}'."
        self.message = message
        if not user:
            user = flask.g.user
        self.user = user
        self.group = group

    def __call__(self, form, field):
        if self.group:
            existing = CoprsLogic.exists_for_group(
                self.group, field.data).first()
        else:
            existing = CoprsLogic.exists_for_user(
                self.user, field.data).first()

        if existing and str(existing.id) != form.id.data:
            raise wtforms.ValidationError(self.message.format(field.data))


class NameCharactersValidator(object):
    def __init__(self, message=None):
        if not message:
            message = "Name must contain only letters, digits, underscores, dashes and dots."
        self.message = message

    def __call__(self, form, field):
        validator = wtforms.validators.Regexp(
                        re.compile(r"^[\w.-]+$"),
                        message=self.message)
        validator(form, field)


class ChrootsValidator(object):
    def __call__(self, form, field):
        # Allow it to be truly optional and has None value
        if not field.data:
            return

        selected = set(field.data.split())
        enabled = set(MockChrootsLogic.active_names())

        if selected - enabled:
            raise wtforms.ValidationError("Such chroot is not available: {}".format(", ".join(selected - enabled)))


class NameNotNumberValidator(object):

    def __init__(self, message=None):
        if not message:
            message = "Project's name can not be just number."
        self.message = message

    def __call__(self, form, field):
        if field.data.isdigit():
            raise wtforms.ValidationError(self.message.format(field.data))


class EmailOrURL(object):

    def __init__(self, message=None):
        if not message:
            message = "{} must be email address or URL"
        self.message = message

    def __call__(self, form, field):
        for validator in [wtforms.validators.Email(), wtforms.validators.URL()]:
            try:
                validator(form, field)
                return True
            except wtforms.ValidationError:
                pass
        raise wtforms.ValidationError(self.message.format(field.name.capitalize()))


class StringListFilter(object):

    def __call__(self, value):
        if not value:
            return ''
        # Replace every whitespace string with one newline
        # Formats ideally for html form filling, use replace('\n', ' ')
        # to get space-separated values or split() to get list
        result = value.strip()
        regex = re.compile(r"\s+")
        return regex.sub(lambda x: '\n', result)


class ValueToPermissionNumberFilter(object):

    def __call__(self, value):
        if value:
            return helpers.PermissionEnum("request")
        return helpers.PermissionEnum("nothing")


class CoprFormFactory(object):

    @staticmethod
    def create_form_cls(mock_chroots=None, user=None, group=None, copr=None):
        class F(FlaskForm):
            # also use id here, to be able to find out whether user
            # is updating a copr if so, we don't want to shout
            # that name already exists
            id = wtforms.HiddenField()
            group_id = wtforms.HiddenField()

            name = wtforms.StringField(
                "Name",
                validators=[
                    wtforms.validators.DataRequired(),
                    NameCharactersValidator(),
                    CoprUniqueNameValidator(user=user, group=group),
                    NameNotNumberValidator()
                ])

            homepage = wtforms.StringField(
                "Homepage",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.URL()])

            contact = wtforms.StringField(
                "Contact",
                validators=[
                    wtforms.validators.Optional(),
                    EmailOrURL()])

            description = wtforms.TextAreaField("Description")

            instructions = wtforms.TextAreaField("Instructions")

            delete_after_days = wtforms.IntegerField(
                "Delete after days",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(min=0, max=60),
                ],
                render_kw={'disabled': bool(copr and copr.persistent)})

            repos = wtforms.TextAreaField(
                "External Repositories",
                validators=[UrlRepoListValidator()],
                filters=[StringListFilter()])

            initial_pkgs = wtforms.TextAreaField(
                "Initial packages to build",
                validators=[
                    UrlListValidator(),
                    UrlSrpmListValidator()],
                filters=[StringListFilter()])

            disable_createrepo = wtforms.BooleanField(default=False,
                    label="Create repositories manually",
                    description="""Repository meta data is normally refreshed
                    after each build.  If you want to do this manually, turn
                    this option on.""",
                    false_values=FALSE_VALUES)

            unlisted_on_hp = wtforms.BooleanField(
                    "Project will not be listed on home page",
                    default=False,
                    false_values=FALSE_VALUES)

            persistent = wtforms.BooleanField(
                    "Protect project and its builds against deletion",
                    description="""Project's builds and the project itself
                    cannot be deleted by any means.  This option is set once and
                    for all (this option can not be changed after project is
                    created).""",
                    render_kw={'disabled': bool(copr)},
                    default=False, false_values=FALSE_VALUES)

            auto_prune = wtforms.BooleanField(
                    "Old builds will be deleted automatically",
                    default=True, false_values=FALSE_VALUES,
                    description="""Build will be deleted only if there is a
                    newer build (with respect to package version) and it is
                    older than 14 days""")

            use_bootstrap_container = wtforms.BooleanField(
                    "Enable mock's use_bootstrap_container experimental feature",
                    description="""This will make the build slower but it has an
                    advantage that the dnf _from_ the given chroot will be used
                    to setup the chroot (otherwise host system dnf and rpm is
                    used)""",
                    default=False,
                    false_values=FALSE_VALUES)

            follow_fedora_branching = wtforms.BooleanField(
                    "Follow Fedora branching",
                    description="""When Fedora is branched from rawhide, the
                    respective chroots for the new branch are automatically
                    created for you (as soon as they are available) as rawhide
                    chroot forks.""",
                    default=True,
                    false_values=FALSE_VALUES)

            multilib = wtforms.BooleanField(
                    "Multilib support",
                    description="""When users enable this copr repository on
                    64bit variant of multilib capable architecture (e.g.
                    x86_64), they will be able to install 32bit variants of the
                    packages (e.g. i386 for x86_64 arch)""",
                    default=False,
                    false_values=FALSE_VALUES)

            # Deprecated, use `enable_net` instead
            build_enable_net = wtforms.BooleanField(
                    "Enable internet access during builds",
                    default=False, false_values=FALSE_VALUES)

            enable_net = wtforms.BooleanField(
                    "Enable internet access during builds",
                    default=False, false_values=FALSE_VALUES)

            module_hotfixes = wtforms.BooleanField(
                    "This repository contains module hotfixes",
                    description="""This will make packages from this project
                    available on along with packages from the active module
                    streams.""",
                    default=False, false_values=FALSE_VALUES)

            @property
            def selected_chroots(self):
                selected = []
                for ch in self.chroots_list:
                    if getattr(self, ch).data:
                        selected.append(ch)
                return selected

            def validate(self):
                if not super(F, self).validate():
                    return False

                if not self.validate_mock_chroots_not_empty():
                    self.errors["chroots"] = ["At least one chroot must be selected"]
                    return False

                if self.persistent.data and self.delete_after_days.data:
                    self.delete_after_days.errors.append(
                        "'delete after' can not be combined with persistent")
                    return False

                return True

            def validate_mock_chroots_not_empty(self):
                have_any = False
                for c in self.chroots_list:
                    if getattr(self, c).data:
                        have_any = True
                return have_any

        F.chroots_list = MockChrootsLogic.active_names()
        F.chroots_list.sort()
        # sets of chroots according to how we should print them in columns
        F.chroots_sets = {}
        for ch in F.chroots_list:
            checkbox_default = False
            if mock_chroots and ch in [x.name for x in mock_chroots]:
                checkbox_default = True

            setattr(F, ch, wtforms.BooleanField(ch, default=checkbox_default, false_values=FALSE_VALUES))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


class CoprDeleteForm(FlaskForm):
    verify = wtforms.StringField(
        "Confirm deleting by typing 'yes'",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Regexp(
                r"^yes$",
                message="Type 'yes' - without the quotes, lowercase.")
        ])


class APICoprDeleteForm(CoprDeleteForm):
    verify = wtforms.BooleanField("Confirm deleting", false_values=FALSE_VALUES)


# @TODO jkadlcik - rewrite via BaseBuildFormFactory after fe-dev-cloud is back online
class BuildFormRebuildFactory(object):
    @staticmethod
    def create_form_cls(active_chroots):
        class F(FlaskForm):
            @property
            def selected_chroots(self):
                selected = []
                for ch in self.chroots_list:
                    if getattr(self, ch).data:
                        selected.append(ch)
                return selected

            memory_reqs = wtforms.IntegerField(
                "Memory requirements",
                validators=[
                    wtforms.validators.NumberRange(
                        min=constants.MIN_BUILD_MEMORY,
                        max=constants.MAX_BUILD_MEMORY)],
                default=constants.DEFAULT_BUILD_MEMORY)

            timeout = wtforms.IntegerField(
                "Timeout",
                validators=[
                    wtforms.validators.NumberRange(
                        min=constants.MIN_BUILD_TIMEOUT,
                        max=constants.MAX_BUILD_TIMEOUT)],
                default=constants.DEFAULT_BUILD_TIMEOUT)

            enable_net = wtforms.BooleanField(false_values=FALSE_VALUES)
            background = wtforms.BooleanField(false_values=FALSE_VALUES)
            project_dirname = wtforms.StringField(default=None)

        F.chroots_list = list(map(lambda x: x.name, active_chroots))
        F.chroots_list.sort()
        F.chroots_sets = {}
        for ch in F.chroots_list:
            setattr(F, ch, wtforms.BooleanField(ch, default=True, false_values=FALSE_VALUES))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


class RebuildPackageFactory(object):
    @staticmethod
    def create_form_cls(active_chroots):
        form = BuildFormRebuildFactory.create_form_cls(active_chroots)
        form.package_name = wtforms.StringField(
            "Package name",
            validators=[wtforms.validators.DataRequired()])
        return form


def cleanup_chroot_blacklist(string):
    if not string:
        return string
    fields = [x.lstrip().rstrip() for x in string.split(',')]
    return ', '.join(fields)


def validate_chroot_blacklist(form, field):
    if field.data:
        string = field.data
        fields = [x.lstrip().rstrip() for x in string.split(',')]
        for field in fields:
            pattern = r'^[a-z0-9-*]+$'
            if not re.match(pattern, field):
                raise wtforms.ValidationError('Pattern "{0}" does not match "{1}"'.format(field, pattern))

            matched = set()
            all_chroots = MockChrootsLogic.active_names()
            for chroot in all_chroots:
                if fnmatch(chroot, field):
                    matched.add(chroot)

            if not matched:
                raise wtforms.ValidationError('no chroot matched by pattern "{0}"'.format(field))

            if matched == all_chroots:
                raise wtforms.ValidationError('patterns are black-listing all chroots')


class BasePackageForm(FlaskForm):
    package_name = wtforms.StringField(
        "Package name",
        validators=[wtforms.validators.DataRequired()])
    webhook_rebuild = wtforms.BooleanField(default=False, false_values=FALSE_VALUES)
    chroot_blacklist = wtforms.StringField(
        "Chroot blacklist",
        filters=[cleanup_chroot_blacklist],
        validators=[
            wtforms.validators.Optional(),
            validate_chroot_blacklist,
        ],
    )
    max_builds = wtforms.IntegerField(
        "Max number of builds",
        description="""Keep only the specified number of the newest-by-id builds
        (garbage collector is run daily)""",
        render_kw={'placeholder': 'Optional - integer, e.g. 10, zero/empty disables'},
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.NumberRange(min=0, max=100)],
        default=None,
    )


class PackageFormScm(BasePackageForm):
    scm_type = wtforms.SelectField(
        "Type",
        choices=[("git", "Git"), ("svn", "SVN")],
        default="git")

    clone_url = wtforms.StringField(
        "Clone url",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.URL()])

    committish = wtforms.StringField(
        "Committish",
        validators=[
            wtforms.validators.Optional()])

    subdirectory = wtforms.StringField(
        "Subdirectory",
        validators=[
            wtforms.validators.Optional()])

    spec = wtforms.StringField(
        "Spec File",
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.Regexp(
                r"^.+\.spec$",
                message="RPM spec file must end with .spec")])

    srpm_build_method = wtforms.SelectField(
        "SRPM build method",
        choices=[(x, x) for x in ["rpkg", "tito", "tito_test", "make_srpm"]],
        default="rpkg")

    @property
    def source_json(self):
        return json.dumps({
            "type": self.scm_type.data,
            "clone_url": self.clone_url.data,
            "subdirectory": self.subdirectory.data,
            "committish": self.committish.data,
            "spec": self.spec.data,
            "srpm_build_method": self.srpm_build_method.data,
        })


class PackageFormPyPI(BasePackageForm):
    pypi_package_name = wtforms.StringField(
        "PyPI package name",
        validators=[wtforms.validators.DataRequired()])

    pypi_package_version = wtforms.StringField(
        "PyPI package version",
        validators=[
            wtforms.validators.Optional(),
        ])

    spec_template = wtforms.SelectField(
        "Spec template",
        choices=[
            ("", "default"),
            ("fedora", "fedora"),
            ("epel7", "epel7"),
            ("mageia", "mageia"),
            ("pld", "pld"),
        ], default="")

    python_versions = MultiCheckboxField(
        'Build for Python',
        choices=[
            ('3', 'python3'),
            ('2', 'python2')
        ],
        default=['3', '2'])

    @property
    def source_json(self):
        return json.dumps({
            "pypi_package_name": self.pypi_package_name.data,
            "pypi_package_version": self.pypi_package_version.data,
            "spec_template": self.spec_template.data,
            "python_versions": self.python_versions.data
        })


class PackageFormRubyGems(BasePackageForm):
    gem_name = wtforms.StringField(
        "Gem Name",
        validators=[wtforms.validators.DataRequired()])

    @property
    def source_json(self):
        return json.dumps({
            "gem_name": self.gem_name.data
        })


class PackageFormTito(BasePackageForm):
    """
    @deprecated
    """
    git_url = wtforms.StringField(
        "Git URL",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.URL()])

    git_directory = wtforms.StringField(
        "Git Directory",
        validators=[
            wtforms.validators.Optional()])

    git_branch = wtforms.StringField(
        "Git Branch",
        validators=[
            wtforms.validators.Optional()])

    tito_test = wtforms.BooleanField(default=False, false_values=FALSE_VALUES)

    @property
    def source_json(self):
        return json.dumps({
            "type": 'git',
            "clone_url": self.git_url.data,
            "committish": self.git_branch.data,
            "subdirectory": self.git_directory.data,
            "spec": '',
            "srpm_build_method": 'tito_test' if self.tito_test.data else 'tito',
        })


class PackageFormMock(BasePackageForm):
    """
    @deprecated
    """
    scm_type = wtforms.SelectField(
        "SCM Type",
        choices=[("git", "Git"), ("svn", "SVN")])

    scm_url = wtforms.StringField(
        "SCM URL",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.URL()])

    scm_branch = wtforms.StringField(
        "Git Branch",
        validators=[
            wtforms.validators.Optional()])

    scm_subdir = wtforms.StringField(
        "Subdirectory",
        validators=[
            wtforms.validators.Optional()])

    spec = wtforms.StringField(
        "Spec File",
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.Regexp(
                r"^.+\.spec$",
                message="RPM spec file must end with .spec")])

    @property
    def source_json(self):
        return json.dumps({
            "type": self.scm_type.data,
            "clone_url": self.scm_url.data,
            "committish": self.scm_branch.data,
            "subdirectory": self.scm_subdir.data,
            "spec": self.spec.data,
            "srpm_build_method": 'rpkg',
        })


class PackageFormDistGit(BasePackageForm):
    """
    @deprecated
    """
    clone_url = wtforms.StringField(
        "Clone Url",
        validators=[wtforms.validators.DataRequired()])

    branch = wtforms.StringField(
        "Branch",
        validators=[wtforms.validators.Optional()])

    @property
    def source_json(self):
        return json.dumps({
            "type": 'git',
            "clone_url": self.clone_url.data,
            "committish": self.branch.data,
            "subdirectory": '',
            "spec": '',
            "srpm_build_method": 'rpkg',
        })


def cleanup_script(string):
    if not string:
        return string

    if string.split('\n')[0].endswith('\r'):
        # This script is most probably coming from the web-UI, where
        # web-browsers mistakenly put '\r\n' as EOL;  and that would just
        # mean that the script is not executable (any line can mean
        # syntax error, but namely shebang would cause 100% fail)
        string = string.replace('\r\n', '\n')

    # And append newline to have a valid unix file.
    if not string.endswith('\n'):
        string += '\n'

    return string


class PackageFormCustom(BasePackageForm):
    script = wtforms.TextAreaField(
        "Script",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(
                max=4096,
                message="Maximum script size is 4kB"),
        ],
        filters=[cleanup_script],
    )

    builddeps = wtforms.StringField(
        "Build dependencies",
        validators=[wtforms.validators.Optional()])

    chroot = wtforms.SelectField(
        'Mock chroot',
        choices=[],
        default='fedora-latest-x86_64',
    )

    resultdir = wtforms.StringField(
        "Result directory",
        validators=[wtforms.validators.Optional()])

    def __init__(self, *args, **kwargs):
        super(PackageFormCustom, self).__init__(*args, **kwargs)
        chroot_objects = models.MockChroot.query.filter(models.MockChroot.is_active).all()

        chroots = [c.name for c in chroot_objects]
        chroots.sort()
        chroots = [(name, name) for name in chroots]

        arches = set()
        for ch in chroot_objects:
            if ch.os_release == 'fedora':
                arches.add(ch.arch)

        self.chroot.choices = []
        if arches:
            self.chroot.choices += [('fedora-latest-' + l, 'fedora-latest-' + l) for l in arches]

        self.chroot.choices += chroots

    @property
    def source_json(self):
        return json.dumps({
            "script": self.script.data,
            "chroot": self.chroot.data,
            "builddeps": self.builddeps.data,
            "resultdir": self.resultdir.data,
        })


class RebuildAllPackagesFormFactory(object):
    def __new__(cls, active_chroots, package_names):
        form_cls = BaseBuildFormFactory(active_chroots, FlaskForm)
        form_cls.packages = MultiCheckboxField(
            "Packages",
            choices=[(name, name) for name in package_names],
            default=package_names,
            validators=[wtforms.validators.DataRequired()])
        return form_cls


class BaseBuildFormFactory(object):
    def __new__(cls, active_chroots, form, package=None):
        class F(form):
            @property
            def selected_chroots(self):
                selected = []
                for ch in self.chroots_list:
                    if getattr(self, ch).data:
                        selected.append(ch)
                return selected

        F.memory_reqs = wtforms.IntegerField(
            "Memory requirements",
            validators=[
                wtforms.validators.Optional(),
                wtforms.validators.NumberRange(
                    min=constants.MIN_BUILD_MEMORY,
                    max=constants.MAX_BUILD_MEMORY)],
            default=constants.DEFAULT_BUILD_MEMORY)

        F.timeout = wtforms.IntegerField(
            "Timeout",
            validators=[
                wtforms.validators.Optional(),
                wtforms.validators.NumberRange(
                    min=constants.MIN_BUILD_TIMEOUT,
                    max=constants.MAX_BUILD_TIMEOUT)],
            default=constants.DEFAULT_BUILD_TIMEOUT)

        F.enable_net = wtforms.BooleanField(false_values=FALSE_VALUES)
        F.background = wtforms.BooleanField(default=False, false_values=FALSE_VALUES)
        F.project_dirname = wtforms.StringField(default=None)

        # overrides BasePackageForm.package_name and is unused for building
        F.package_name = wtforms.StringField()

        # fill chroots based on project settings
        F.chroots_list = [x.name for x in active_chroots]
        F.chroots_list.sort()
        F.chroots_sets = {}

        package_chroots = set(F.chroots_list)
        if package:
            package_chroots = set([ch.name for ch in package.chroots])

        for ch in F.chroots_list:
            default = ch in package_chroots
            setattr(F, ch, wtforms.BooleanField(ch, default=default, false_values=FALSE_VALUES))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]
        return F


class BuildFormScmFactory(object):
    def __new__(cls, active_chroots, package=None):
        return BaseBuildFormFactory(active_chroots, PackageFormScm, package)


class BuildFormTitoFactory(object):
    """
    @deprecated
    """
    def __new__(cls, active_chroots):
        return BaseBuildFormFactory(active_chroots, PackageFormTito)


class BuildFormMockFactory(object):
    """
    @deprecated
    """
    def __new__(cls, active_chroots):
        return BaseBuildFormFactory(active_chroots, PackageFormMock)


class BuildFormPyPIFactory(object):
    def __new__(cls, active_chroots, package=None):
        return BaseBuildFormFactory(active_chroots, PackageFormPyPI, package)


class BuildFormRubyGemsFactory(object):
    def __new__(cls, active_chroots, package=None):
        return BaseBuildFormFactory(active_chroots, PackageFormRubyGems, package)


class BuildFormDistGitFactory(object):
    def __new__(cls, active_chroots):
        return BaseBuildFormFactory(active_chroots, PackageFormDistGit)


class BuildFormUploadFactory(object):
    def __new__(cls, active_chroots):
        form = BaseBuildFormFactory(active_chroots, FlaskForm)
        form.pkgs = FileField('srpm', validators=[
            FileRequired(),
            SrpmValidator()])
        return form


class BuildFormCustomFactory(object):
    def __new__(cls, active_chroots, package=None):
        return BaseBuildFormFactory(active_chroots, PackageFormCustom, package)


class BuildFormUrlFactory(object):
    def __new__(cls, active_chroots):
        form = BaseBuildFormFactory(active_chroots, FlaskForm)
        form.pkgs = wtforms.TextAreaField(
            "Pkgs",
            validators=[
                wtforms.validators.DataRequired(message="URLs to packages are required"),
                UrlListValidator(),
                UrlSrpmListValidator()],
            filters=[StringListFilter()])
        return form


class ModuleFormUploadFactory(FlaskForm):
    modulemd = FileField("modulemd", validators=[
        FileRequired(),
        # @TODO Validate modulemd.yaml file
    ])

    create = wtforms.BooleanField("create", default=True, false_values=FALSE_VALUES)
    build = wtforms.BooleanField("build", default=True, false_values=FALSE_VALUES)


class ModuleBuildForm(FlaskForm):
    modulemd = FileField("modulemd")
    scmurl = wtforms.StringField()
    branch = wtforms.StringField()


class PagureIntegrationForm(FlaskForm):
    repo_url = wtforms.StringField("repo_url", default='')
    api_key = wtforms.StringField("api_key", default='')

    def __init__(self, api_key=None, repo_url=None, *args, **kwargs):
        super(PagureIntegrationForm, self).__init__(*args, **kwargs)
        if api_key != None:
            self.api_key.data = api_key
        if repo_url != None:
            self.repo_url.data = repo_url


class ChrootForm(FlaskForm):

    """
    Validator for editing chroots in project
    (adding packages to minimal chroot)
    """

    buildroot_pkgs = wtforms.StringField("Packages")

    repos = wtforms.TextAreaField('Repos',
                                  validators=[UrlRepoListValidator(),
                                              wtforms.validators.Optional()],
                                  filters=[StringListFilter()])

    comps = FileField("comps_xml")

    with_opts = wtforms.StringField("With options")
    without_opts = wtforms.StringField("Without options")


class CoprChrootExtend(FlaskForm):
    extend = wtforms.StringField("Chroot name")
    expire = wtforms.StringField("Chroot name")


class CoprLegalFlagForm(FlaskForm):
    comment = wtforms.TextAreaField("Comment")


class PermissionsApplierFormFactory(object):

    @staticmethod
    def create_form_cls(permission=None):
        class F(FlaskForm):
            pass

        builder_default = False
        admin_default = False

        if permission:
            if permission.copr_builder != helpers.PermissionEnum("nothing"):
                builder_default = True
            if permission.copr_admin != helpers.PermissionEnum("nothing"):
                admin_default = True

        setattr(F, "copr_builder",
                wtforms.BooleanField(
                    default=builder_default,
                    false_values=FALSE_VALUES,
                    filters=[ValueToPermissionNumberFilter()]))

        setattr(F, "copr_admin",
                wtforms.BooleanField(
                    default=admin_default,
                    false_values=FALSE_VALUES,
                    filters=[ValueToPermissionNumberFilter()]))

        return F


class PermissionsFormFactory(object):

    """Creates a dynamic form for given set of copr permissions"""
    @staticmethod
    def create_form_cls(permissions):
        class F(FlaskForm):
            pass

        for perm in permissions:
            builder_choices = helpers.PermissionEnum.choices_list()
            admin_choices = helpers.PermissionEnum.choices_list()

            builder_default = perm.copr_builder
            admin_default = perm.copr_admin

            setattr(F, "copr_builder_{0}".format(perm.user.id),
                    wtforms.SelectField(
                        choices=builder_choices,
                        default=builder_default,
                        coerce=int))

            setattr(F, "copr_admin_{0}".format(perm.user.id),
                    wtforms.SelectField(
                        choices=admin_choices,
                        default=admin_default,
                        coerce=int))

        return F


class CoprModifyForm(FlaskForm):
    description = wtforms.TextAreaField('Description',
                                        validators=[wtforms.validators.Optional()])

    instructions = wtforms.TextAreaField('Instructions',
                                         validators=[wtforms.validators.Optional()])

    chroots = wtforms.TextAreaField('Chroots',
                                    validators=[wtforms.validators.Optional(), ChrootsValidator()])

    repos = wtforms.TextAreaField('External Repositories',
                                  validators=[UrlRepoListValidator(),
                                              wtforms.validators.Optional()],
                                  filters=[StringListFilter()])

    disable_createrepo = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    unlisted_on_hp = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    auto_prune = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    use_bootstrap_container = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    follow_fedora_branching = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    follow_fedora_branching = wtforms.BooleanField(default=True, false_values=FALSE_VALUES)
    delete_after_days = wtforms.IntegerField(
        validators=[wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(min=-1, max=60)],
        filters=[(lambda x : -1 if x is None else x)])

    # Deprecated, use `enable_net` instead
    build_enable_net = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    enable_net = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)
    multilib = wtforms.BooleanField(validators=[wtforms.validators.Optional()], false_values=FALSE_VALUES)


class CoprForkFormFactory(object):
    @staticmethod
    def create_form_cls(copr, user, groups):
        class F(FlaskForm):
            source = wtforms.StringField(
                "Source",
                default=copr.full_name)

            owner = wtforms.SelectField(
                "Fork owner",
                choices=[(user.name, user.name)] + [(g.at_name, g.at_name) for g in groups],
                default=user.name,
                validators=[wtforms.validators.DataRequired()])

            name = wtforms.StringField(
                "Fork name",
                default=copr.name,
                validators=[wtforms.validators.DataRequired(), NameCharactersValidator()])

            confirm = wtforms.BooleanField(
                "Confirm",
                false_values=FALSE_VALUES,
                default=False)
        return F


class ModifyChrootForm(ChrootForm):
    buildroot_pkgs = wtforms.StringField('Additional packages to be always present in minimal buildroot')
    repos = wtforms.TextAreaField('Additional repos to be used for builds in chroot',
                                  validators=[UrlRepoListValidator(),
                                              wtforms.validators.Optional()],
                                  filters=[StringListFilter()])
    comps = None
    upload_comps = FileField("Upload comps.xml")
    delete_comps = wtforms.BooleanField("Delete comps.xml", false_values=FALSE_VALUES)


class PinnedCoprsForm(FlaskForm):
    copr_ids = wtforms.SelectMultipleField(wtforms.IntegerField("Pinned Copr ID"))

    def validate(self):
        if any([i and not i.isnumeric() for i in self.copr_ids.data]):
            self.errors["coprs"] = ["Unexpected value selected"]
            return False

        limit = app.config["PINNED_PROJECTS_LIMIT"]
        if len(self.copr_ids.data) > limit:
            self.errors["coprs"] = ["Too many pinned projects. Limit is {}!".format(limit)]
            return False

        if len(list(filter(None, self.copr_ids.data))) != len(set(filter(None, self.copr_ids.data))):
            self.errors["coprs"] = ["You can pin a particular project only once"]
            return False

        return True


class AdminPlaygroundForm(FlaskForm):
    playground = wtforms.BooleanField("Playground", false_values=FALSE_VALUES)


class AdminPlaygroundSearchForm(FlaskForm):
    project = wtforms.StringField("Project")


class GroupUniqueNameValidator(object):

    def __init__(self, message=None):
        if not message:
            message = "Group with the alias '{}' already exists."
        self.message = message

    def __call__(self, form, field):
        if UsersLogic.group_alias_exists(field.data):
            raise wtforms.ValidationError(self.message.format(field.data))


class ActivateFasGroupForm(FlaskForm):

    name = wtforms.StringField(
        validators=[
            wtforms.validators.Regexp(
                re.compile(r"^[\w.-]+$"),
                message="Name must contain only letters,"
                "digits, underscores, dashes and dots."),
            GroupUniqueNameValidator()
        ]
    )


class CreateModuleForm(FlaskForm):
    builds = wtforms.FieldList(wtforms.StringField("Builds ID list"))
    packages = wtforms.FieldList(wtforms.StringField("Packages list"))
    filter = wtforms.FieldList(wtforms.StringField("Package Filter"))
    api = wtforms.FieldList(wtforms.StringField("Module API"))
    profile_names = wtforms.FieldList(wtforms.StringField("Install Profiles"), min_entries=2)
    profile_pkgs = wtforms.FieldList(wtforms.FieldList(wtforms.StringField("Install Profiles")), min_entries=2)

    def __init__(self, copr=None, *args, **kwargs):
        self.copr = copr
        super(CreateModuleForm, self).__init__(*args, **kwargs)

    def validate(self):
        if not FlaskForm.validate(self):
            return False

        # Profile names should be unique
        names = [x for x in self.profile_names.data if x]
        if len(set(names)) < len(names):
            self.errors["profiles"] = ["Profile names must be unique"]
            return False

        # WORKAROUND
        # profile_pkgs are somehow sorted so if I fill profile_name in the first box and
        # profile_pkgs in seconds box, it is sorted and validated correctly
        for i in range(0, len(self.profile_names.data)):
            # If profile name is not set, then there should not be any packages in this profile
            if not flask.request.form["profile_names-{}".format(i)]:
                if [j for j in range(0, len(self.profile_names)) if "profile_pkgs-{}-{}".format(i, j) in flask.request.form]:
                    self.errors["profiles"] = ["Missing profile name"]
                    return False
        return True


class ModuleRepo(FlaskForm):
    owner = wtforms.StringField("Owner Name", validators=[wtforms.validators.DataRequired()])
    copr = wtforms.StringField("Copr Name", validators=[wtforms.validators.DataRequired()])
    name = wtforms.StringField("Name", validators=[wtforms.validators.DataRequired()])
    stream = wtforms.StringField("Stream", validators=[wtforms.validators.DataRequired()])
    version = wtforms.IntegerField("Version", validators=[wtforms.validators.DataRequired()])
    arch = wtforms.StringField("Arch", validators=[wtforms.validators.DataRequired()])
