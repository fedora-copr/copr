import os
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

from coprs import app
from coprs import helpers
from coprs import models
from coprs.logic.coprs_logic import CoprsLogic, MockChrootsLogic
from coprs.logic.users_logic import UsersLogic
from coprs.logic.dist_git_logic import DistGitLogic
from coprs.logic.complex_logic import ComplexLogic
from coprs import exceptions

from wtforms import ValidationError

FALSE_VALUES = {False, "false", ""}


class NoneFilter():
    def __init__(self, default):
        self.default = default

    def __call__(self, value):
        if value in [None, 'None']:
            return self.default
        return value

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
    # pylint: disable=too-many-return-statements
    if source_type_text == 'scm':
        return PackageFormScm
    elif source_type_text == 'pypi':
        return PackageFormPyPI
    elif source_type_text == 'rubygems':
        return PackageFormRubyGems
    elif source_type_text == "custom":
        return PackageFormCustom
    elif source_type_text == "distgit":
        return PackageFormDistGitSimple
    else:
        raise exceptions.UnknownSourceTypeException("Invalid source type")


def create_mock_bootstrap_field(level):
    """
    Select-box for the bootstrap configuration in chroot/project form
    """

    choices = []
    default_choices = [
        ('default', 'Use default configuration from mock-core-configs.rpm'),
        ('off', 'Disable'),
        ('on', 'Enable'),
        ('image', 'Initialize by default pre-configured container image'),
    ]

    if level == 'chroot':
        choices.append(("unchanged", "Use project settings"))
        choices.extend(default_choices)
        choices.append(('custom_image',
                        'Initialize by custom bootstrap image (specified '
                        'in the "Mock bootstrap image" field below)'))

    elif level == 'build':
        choices.append(("unchanged", "Use project/chroot settings"))
        choices.extend(default_choices)

    else:
        choices.extend(default_choices)

    return wtforms.SelectField(
        "Mock bootstrap",
        choices=choices,
        validators=[wtforms.validators.Optional()],
        # Replace "None" with None (needed on Fedora <= 32)
        filters=[NoneFilter(None)],
    )


def create_isolation_field(level):
    """
    Select-box for the isolation option configuration in build/project form
    """

    choices = []
    default_choices = [
        ('default', 'Use default configuration from mock-core-configs.rpm'),
        ('nspawn', 'systemd-nspawn'),
        ('simple', 'simple chroot'),
    ]

    if level == "build":
        choices.append(("unchanged", "Use project/chroot settings"))
    elif level == "chroot":
        choices.append(("unchanged", "Use project settings"))

    choices.extend(default_choices)

    return wtforms.SelectField(
        "Build isolation",
        choices=choices,
        validators=[wtforms.validators.Optional()],
        filters=[NoneFilter(None)],
        description="Choose the isolation method for running commands in buildroot"
    )


def create_mock_bootstrap_image_field():
    """
    Mandatory bootstrap-image field when the bootstrap select-box is set to a
    custom image option.
    """
    return wtforms.StringField(
        "Mock bootstrap image",
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.Regexp(
                r"^\w+(:\w+)?$",
                message=("Enter valid bootstrap image id "
                         "(<name>[:<tag>], e.g. fedora:33)."))],
        filters=[
            lambda x: None if not x else x
        ],
    )


class BooleanFieldOptional(wtforms.BooleanField):
    """
    The same as BooleanField, but we make sure that None is used for self.data
    instead of False when no data were submitted in the form for this field.
    From web-ui it isn't normal situation, but from command-line client and
    Python API it is pretty normal that some fields are not set in POST data.
    And sometimes it is convenient to have three-state checkbox
    (True|False|None).
    """
    def process_formdata(self, valuelist):
        """ override parent's self.data decision when no value is sent """
        super().process_formdata(valuelist)
        if not valuelist:
            # pylint: disable=attribute-defined-outside-init
            self.data = None


class MultiCheckboxField(wtforms.SelectMultipleField):
    widget = wtforms.widgets.ListWidget(prefix_label=False)
    option_widget = wtforms.widgets.CheckboxInput()


class ChrootsField(MultiCheckboxField):
    """
    A list of chroot checkboxes. It doesn't accept any other value than
    currently active mock chroot names. When `copr` is specified, the checkboxes
    are ticked based on the currently enabled chroots in that project.
    """
    # pylint: disable=too-few-public-methods

    def __init__(self, label="", validators=None, copr=None, **kwargs):
        super().__init__(label, validators, **kwargs)
        self.label = label or "Chroots"

        active_names = sorted(MockChrootsLogic.active_names())
        self.choices = [(ch, ch) for ch in active_names]

        copr_mock_chroots = copr.active_chroots if copr else []
        copr_chroot_names = [ch.name for ch in copr_mock_chroots]
        self.default = [ch for ch in active_names if ch in copr_chroot_names]


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
                message = "You already have a project named '{}'."
            else:
                message = "Group {} ".format(group) + "already has a project named '{}'."
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


class CoprUniqueNameValidator2:
    """
    Validate that that Copr project name User gave us doesn't
    cause duplicity.

    This validator can only be used in CoprBaseForm descendants.

    TODO: Replace all occurrences of CoprUniqueNameValidator with this.
    """
    usr_msg = "You already have"
    grp_msg = "Group '{}' already has"

    def __call__(self, form, field):
        msg = self.usr_msg
        if form.group:
            msg = self.grp_msg.format(form.group.name)
            existing = CoprsLogic.exists_for_group(
                form.group, field.data).first()
        else:
            existing = CoprsLogic.exists_for_user(
                form.user, field.data).first()

        if existing:
            msg = msg + " a project named \"{}\"".format(existing.name)
            raise wtforms.ValidationError(msg)


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

class ModuleEnableNameValidator(object):

    def __call__(self, form, field):
        already_enabled = {}
        for module in form.module_toggle.data.split(","):
            if module == "":
                return True

            try:
                module_name, stream = module.strip().split(":")
            except ValueError:
                raise ValidationError(
                    message=(
                        "Module name '{0}' must consist of two parts separated "
                        "with colon, e.g. module:stream"
                    ).format(module))

            pattern = re.compile(re.compile(r"^([a-zA-Z0-9-_!][^\ ]*)$"))
            if pattern.match(module_name) is None:
                raise ValidationError(message=(
                    "Module name '{0}' must contain only letters, digits, "
                    "dashes, underscores.").format(module_name))

            if module_name in already_enabled:
                raise ValidationError("Module name '{0}' specified multiple "
                                      "times".format(module_name))
            else:
                already_enabled[module_name] = True

            if pattern.match(stream) is None:
                raise ValidationError(message=(
                    "Stream part of module name '{0}' must contain only "
                    "letters, digits, dashes, underscores.").format(stream))

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

class StringWhiteCharactersFilter(object):

    def __call__(self, value):
        if not value:
            return ''

        modules = [module.strip() for module in value.split(",")]
        # to remove empty strings
        modules = [m for m in modules if m]

        return ", ".join(module for module in modules if module != "")

class ValueToPermissionNumberFilter(object):

    def __call__(self, value):
        if value:
            return helpers.PermissionEnum("request")
        return helpers.PermissionEnum("nothing")

class StripUrlSchemaListFilter():
    """
    Strip the URL schema if present for a list of forge projects.
    """

    def __call__(self, value):
        if not value:
            return ''

        items = value.split()
        result = []

        for item in items:
            parsed_url = urlparse(item)
            result.append(parsed_url.netloc + parsed_url.path)

        return "\n".join(result)

def _optional_checkbox_filter(data):
    if data in [True, 'true']:
        return True
    if data in [False, 'false']:
        return False
    return None


class EmptyStringToNone:
    """ Transform empty text field to None value """
    def __call__(self, value):
        if value is None:
            return None
        if value.strip() == "":
            return None
        return value


class BaseForm(FlaskForm):
    """
    Base class for all of our forms. For example, WTForms doesn't automatically
    remove leading and trailing whitespace from fields, which causes nasty
    bugs like #2223
    """
    class Meta:
        # pylint: disable=missing-class-docstring
        # pylint: disable=missing-function-docstring
        # pylint: disable=no-self-use

        def bind_field(self, form, unbound_field, options):
            filters = unbound_field.kwargs.get("filters", [])

            # It doesn't make sense to strip whitespace for BooleanField,
            # IntegerField, etc. But we don't want to strip whitespace from
            # TextAreaField either, because we want to preserve \n at their end.
            # We also get custom scripts via TextAreaField and we ideally don't
            # want to modify them at all
            if unbound_field.field_class == wtforms.StringField:
                filters.append(strip_whitespace_filter)

            return unbound_field.bind(form=form, filters=filters, **options)


def strip_whitespace_filter(value):
    """
    Remove leading and trailing whitespace from a field
    """
    if value is not None and hasattr(value, "strip"):
        return value.strip()
    return value


class CoprBaseForm(BaseForm):
    """
    All forms that modify Copr project should inherit from this.
    """

    def __init__(self, *args, user=None, group=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.group = group


class CoprFedoraReviewForm(CoprBaseForm):
    """
    Simplified Copr form for FedoraReview-only project.
    """
    name = wtforms.StringField(
        "Name",
        validators=[
            wtforms.validators.DataRequired(),
            NameCharactersValidator(),
            CoprUniqueNameValidator2(),
            NameNotNumberValidator()
        ])


class CoprForm(BaseForm):
    """
    Base form class for adding and modifying projects
    """
    # pylint: disable=too-few-public-methods

    chroots = ChrootsField()

    description = wtforms.TextAreaField("Description")

    instructions = wtforms.TextAreaField("Instructions")

    homepage = wtforms.StringField(
        "Homepage",
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.URL()],
        filters=[EmptyStringToNone()])

    contact = wtforms.StringField(
        "Contact",
        validators=[
            wtforms.validators.Optional(),
            EmailOrURL()],
        filters=[EmptyStringToNone()])

    delete_after_days = wtforms.IntegerField(
        "Delete after days",
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.NumberRange(min=-1, max=60)
        ],
        filters=[(lambda x : -1 if x is None else x)])

    repos = wtforms.TextAreaField(
        "External Repositories",
        validators=[UrlRepoListValidator()],
        filters=[StringListFilter()])

    runtime_dependencies = wtforms.TextAreaField(
        "Runtime dependencies",
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

    auto_prune = wtforms.BooleanField(
            "Old builds will be deleted automatically",
            default=True, false_values=FALSE_VALUES,
            description="""Build will be deleted only if there is a
            newer build (with respect to package version) and it is
            older than 14 days""")

    use_bootstrap_container = wtforms.StringField(
        "backward-compat-only: old bootstrap",
        validators=[wtforms.validators.Optional()],
        filters=[_optional_checkbox_filter])

    bootstrap = create_mock_bootstrap_field("project")

    isolation = create_isolation_field("project")

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

    fedora_review = wtforms.BooleanField(
            "Run fedora-review tool for packages in this project",
            description="""When submitting new package to Fedora, it
            needs to comply with Fedora Packaging Guidelines. Use
            fedora-review tool to help you discover packaging errors.
            Failing fedora-review will not fail the build itself.""",
            default=False, false_values=FALSE_VALUES)

    appstream = wtforms.BooleanField(
            "Generate AppStream metadata",
            description="""Generate AppStream metadata for this project.
            Generating metadata slows down the builds in large Copr projects.""",
            default=True, false_values=FALSE_VALUES)

    packit_forge_projects_allowed = wtforms.TextAreaField(
        "Packit allowed forge projects",
        filters=[StringListFilter(), StripUrlSchemaListFilter()],
        validators=[wtforms.validators.Optional()],)

    @property
    def errors(self):
        """
        Current stable version of WTForms's `Form` doesn't allow to set
        form-level errors. Let's workaround it in a way, that is
        implemented in the development branch.

        2.2.1 (Fedora 31/32)
            `form.errors["whatever"] = ["Some message"]` could be done

        2.3.1 (Fedora 33)
            The previous solution does nothing and there is no way to
            have form-level errors. The only way to set errors is via
            `form.some_field.errors.append("Some message")`. We are
            reimplementing `errors` property to behave like in 3.0.0

        3.0.0 (Fedora ??)
            The `form.form_errors` field can be set. This list will be
            added to the resulting `errors` value and accessible as
            `form.errors[None]`.

            RFE: https://github.com/wtforms/wtforms/issues/55
            PR: https://github.com/wtforms/wtforms/pull/595
            Release notes: https://github.com/wtforms/wtforms/blob/master/CHANGES.rst#version-300
        """

        # I don't understand pylint here, FlaskForm clearly has `errors` property
        errors = super().errors.copy() # pylint: disable=no-member
        if hasattr(self, "form_errors"):
            errors[None] = self.form_errors  # pylint: disable=no-member
        return errors


class CoprFormFactory(object):

    @staticmethod
    def create_form_cls(user=None, group=None, copr=None):
        class F(CoprForm):
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

            persistent = wtforms.BooleanField(
                    "Protect project and its builds against deletion",
                    description="""Project's builds and the project itself
                    cannot be deleted by any means.  This option is set once and
                    for all (this option can not be changed after project is
                    created).""",
                    render_kw={'disabled': bool(copr)},
                    default=False, false_values=FALSE_VALUES)

            # We are redefining the original `CoprForm` field because this
            # requires `copr.persistent`
            delete_after_days = wtforms.IntegerField(
                "Delete after days",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(min=0, max=60),
                ],
                render_kw={'disabled': bool(copr and copr.persistent)})

            # We are redefining the original `CoprForm` field because we need to set
            # a list of default chroots based on `copr`
            chroots = ChrootsField(copr=copr)

            @property
            def selected_chroots(self):
                return self.chroots.data

            def validate(self):
                if not super(F, self).validate():
                    return False

                if not self.validate_mock_chroots_not_empty():
                    self.form_errors = ["At least one chroot must be selected"]
                    return False

                if self.persistent.data and self.delete_after_days.data:
                    self.delete_after_days.errors.append(
                        "'delete after' can not be combined with persistent")
                    return False

                return True

            def validate_mock_chroots_not_empty(self):
                return bool(self.chroots.data)

        return F


class CoprDeleteForm(BaseForm):
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

def seconds_to_pretty_hours(sec):
    minutes = round(sec / 60)
    hours = minutes // 60
    minutes = minutes % 60
    return hours if not minutes else "{}:{:02d}".format(hours, minutes)


class BuildFormRebuildFactory(object):
    # TODO: drop, and use _get_build_form directly
    @staticmethod
    def create_form_cls(active_chroots):
        return _get_build_form(active_chroots, BaseForm)


class RebuildPackageFactory(object):
    @staticmethod
    def create_form_cls(active_chroots):
        form = BuildFormRebuildFactory.create_form_cls(active_chroots)
        # pylint: disable=attribute-defined-outside-init
        form.package_name = wtforms.StringField(
            "Package name",
            validators=[wtforms.validators.DataRequired()])
        return form


def cleanup_chroot_denylist(string):
    """ Filter invalid values out from BasePackageForm.chroot_denylist field """

    if not string:
        return string
    fields = [x.lstrip().rstrip() for x in string.split(',')]
    return ', '.join(fields)


def validate_chroot_denylist(_form, field):
    """ Validate BasePackageForm.chroot_denylist field """

    if field.data:
        string = field.data
        items = [x.lstrip().rstrip() for x in string.split(',')]
        for item in items:
            pattern = r'^[a-z0-9-_*]+$'
            if not re.match(pattern, item):
                raise wtforms.ValidationError('Pattern "{0}" does not match "{1}"'.format(item, pattern))

            matched = set()
            all_chroots = MockChrootsLogic.active_names()
            for chroot in all_chroots:
                if fnmatch(chroot, item):
                    matched.add(chroot)

            if not matched:
                raise wtforms.ValidationError('no chroot matched by pattern "{0}"'.format(item))

            if matched == all_chroots:
                raise wtforms.ValidationError('patterns are deny-listing all chroots')


class BasePackageForm(BaseForm):
    package_name_regex = r"^[-+_.a-zA-Z0-9]+$"

    package_name = wtforms.StringField(
        "Package name",
        validators=[
            wtforms.validators.Length(
                max=helpers.db_column_length(models.Package.name)
            ),
            wtforms.validators.Regexp(
                re.compile(package_name_regex),
                message="Please enter a valid package name in " \
                       + package_name_regex)]
    )

    webhook_rebuild = wtforms.BooleanField(default=False, false_values=FALSE_VALUES)
    chroot_denylist = wtforms.StringField(
        "Chroot denylist",
        filters=[cleanup_chroot_denylist],
        validators=[
            wtforms.validators.Optional(),
            validate_chroot_denylist,
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
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(
                max=(helpers.db_column_length(models.Package.name)
                     - len("python-"))
            ),
        ])

    pypi_package_version = wtforms.StringField(
        "PyPI package version",
        validators=[
            wtforms.validators.Optional(),
        ])

    spec_generator = wtforms.SelectField(
        "Spec generator",
        choices=[
            ("pyp2rpm", "pyp2rpm"),
            ("pyp2spec", "pyp2spec"),
        ], default="pyp2rpm")

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
        default=['3'])

    @property
    def source_json(self):
        return json.dumps({
            "pypi_package_name": self.pypi_package_name.data,
            "pypi_package_version": self.pypi_package_version.data,
            "spec_generator": self.spec_generator.data,
            "spec_template": self.spec_template.data,
            "python_versions": self.python_versions.data
        })


class PackageFormRubyGems(BasePackageForm):
    gem_name = wtforms.StringField(
        "Gem Name",
        validators=[
            wtforms.validators.DataRequired(),
            wtforms.validators.Length(
                max=(helpers.db_column_length(models.Package.name)
                     - len("rubygem-"))
            ),
        ])

    @property
    def source_json(self):
        return json.dumps({
            "gem_name": self.gem_name.data
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

    repos = wtforms.TextAreaField(
        "External repositories for build dependencies",
        validators=[UrlRepoListValidator()],
        filters=[StringListFilter()])

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
            "repos": self.repos.data,
        })


class DistGitValidator(object):
    def __call__(self, form, field):
        if field.data not in field.distgit_choices:
            message = "DistGit ID must be one of: {}".format(
                ", ".join(field.distgit_choices))
            raise wtforms.ValidationError(message)




class DistGitSelectField(wtforms.SelectField):
    """ Select-box for picking (default) dist git instance """

    # pylint: disable=too-few-public-methods
    def __init__(self, validators=None, filters=None, **kwargs):
        if not validators:
            validators = []
        if not filters:
            filters = []

        self.distgit_choices = [x.name for x in DistGitLogic.ordered().all()]
        self.distgit_default = self.distgit_choices[0]

        validators.append(DistGitValidator())
        filters.append(NoneFilter(self.distgit_default))

        super().__init__(
            label="DistGit instance",
            validators=validators,
            filters=filters,
            choices=[(x, x) for x in self.distgit_choices],
            **kwargs,
        )


class PackageFormDistGitSimple(BasePackageForm):
    """
    This represents basically a variant of the SCM method, but with a very
    trivial user interface.
    """
    distgit = DistGitSelectField()

    committish = wtforms.StringField(
        "Committish",
        validators=[wtforms.validators.Optional()],
        render_kw={
            "placeholder": "Optional - Specific branch, tag, or commit that "
                           "you want to build from"},
    )

    namespace = wtforms.StringField(
        "DistGit namespace",
        validators=[wtforms.validators.Optional()],
        default=None,
        filters=[lambda x: None if not x else os.path.normpath(x)],
        description=(
            "Some dist-git instances have the git repositories "
            "namespaced - e.g. you need to specify '@copr/copr' for "
            "the <a href='https://copr-dist-git.fedorainfracloud.org/"
            "cgit/@copr/copr/copr-cli.git/tree/copr-cli.spec'>"
            "@copr/copr/copr-cli</a> Fedora Copr package. When building from "
            "a fork in the Fedora DistGit intance, you need to specify "
            "e.g. 'forks/someuser'."
        ),
        render_kw={
            "placeholder": "Optional - string, e.g. '@copr/copr', or 'forks/someuser'"},
    )

    build_requires_package_name = True

    @property
    def source_json(self):
        """ Source json stored in DB in Package.source_json """
        data = {
            "clone_url": self.clone_url(),
        }

        if self.distgit.data:
            data["distgit"] = self.distgit.data

        for field_name in ["distgit", "namespace", "committish"]:
            field = getattr(self, field_name)
            if field.data:
                data[field_name] = field.data

        return json.dumps(data)

    def clone_url(self):
        """ One-time generate the clone_url from the form data """
        return DistGitLogic.get_clone_url(self.distgit.data,
                                          self.package_name.data,
                                          self.namespace.data)

    def validate(self):
        """
        Try to check that we can generate clone_url from distgit, namespace and
        package.  This can not be done by single-field-context validator.
        """
        if not super().validate():
            return False

        try:
            self.clone_url()
        except Exception as e:  # pylint: disable=broad-except
            self.distgit.errors.append(
                "Can not validate DistGit input: {}".format(str(e))
            )
            return False

        return True


class RebuildAllPackagesFormFactory(object):
    def __new__(cls, active_chroots, package_names):
        form_cls = _get_build_form(active_chroots, BaseForm)
        form_cls.packages = MultiCheckboxField(
            "Packages",
            choices=[(name, name) for name in package_names],
            default=package_names,
            validators=[wtforms.validators.DataRequired()])
        form_cls.only_package_chroots = wtforms.BooleanField(
            label="Respect package-level chroot list configuration",
            description=(
                "The final set of chroot builds submitted for a particular "
                "package will be an <strong>intersection</strong> of the "
                "chroot list <strong>selected below</strong> "
                "and the chroots selected <strong>per package</strong>. "
                "If not set, builds for all chroots selected below will "
                "be submitted."
            ),
            default=True,
            false_values=FALSE_VALUES,
        )
        return form_cls


def _get_build_form(active_chroots, form, package=None):
    class F(form):
        @property
        def selected_chroots(self):
            chroots = self.chroots.data or []
            if self.exclude_chroots.data:
                chroots = set(chroots or self.chroots_list)
                chroots -= set(self.exclude_chroots.data)
                return list(chroots)
            return chroots


    F.timeout = wtforms.IntegerField(
        "Timeout",
        description="Optional - number of seconds we allow the builds to run, default is {0} ({1}h)".format(
            app.config["DEFAULT_BUILD_TIMEOUT"], seconds_to_pretty_hours(app.config["DEFAULT_BUILD_TIMEOUT"])),
        validators=[
            wtforms.validators.Optional(),
            wtforms.validators.NumberRange(
                min=app.config["MIN_BUILD_TIMEOUT"],
                max=app.config["MAX_BUILD_TIMEOUT"])],
        default=app.config["DEFAULT_BUILD_TIMEOUT"])

    F.enable_net = BooleanFieldOptional(false_values=FALSE_VALUES)
    F.background = wtforms.BooleanField(default=False, false_values=FALSE_VALUES)
    F.project_dirname = wtforms.StringField(default=None)
    F.bootstrap = create_mock_bootstrap_field("build")
    F.isolation = create_isolation_field("build")

    # Overrides BasePackageForm.package_name, it is usually unused for
    # building
    if not getattr(F, "build_requires_package_name", None):
        F.package_name = wtforms.StringField()

    # fill chroots based on project settings
    F.chroots_list = [x.name for x in active_chroots]
    F.chroots_list.sort()

    package_chroots = set(F.chroots_list)
    if package:
        package_chroots = set([ch.name for ch in package.chroots])

    F.chroots = MultiCheckboxField(
        "Chroots",
        choices=[(ch, ch) for ch in F.chroots_list],
        default=[ch for ch in F.chroots_list if ch in package_chroots])

    F.exclude_chroots = MultiCheckboxField(
        "Exclude Chroots",
        choices=[(ch, ch) for ch in F.chroots_list],
        default=[])

    F.after_build_id = wtforms.IntegerField(
        "Batch-build after",
        description=(
            "Optional - Build after the batch containing "
            "the Build ID build."
        ),
        validators=[
            wtforms.validators.Optional()],
        render_kw={'placeholder': 'Build ID'},
        filters=[NoneFilter(None)],
    )

    F.with_build_id = wtforms.IntegerField(
        "Batch-build with",
        description=(
            "Optional - Build in the same batch with the Build ID build"
        ),
        render_kw={'placeholder': 'Build ID'},
        validators=[
            wtforms.validators.Optional()],
        filters=[NoneFilter(None)],
    )

    F.packit_forge_project = wtforms.StringField(default=None)

    def _validate_batch_opts(form, field):
        counterpart = form.with_build_id
        modifies = False
        if counterpart == field:
            counterpart = form.after_build_id
            modifies = True

        if counterpart.data:
            raise wtforms.ValidationError(
                "Only one batch option can be specified")

        build_id = field.data
        if not build_id:
            return

        build_id = int(build_id)
        build = models.Build.query.get(build_id)
        if not build:
            raise wtforms.ValidationError(
                "Build {} not found".format(build_id))
        batch_error = build.batching_user_error(flask.g.user, modifies)
        if batch_error:
            raise wtforms.ValidationError(batch_error)

    F.validate_with_build_id = _validate_batch_opts
    F.validate_after_build_id = _validate_batch_opts

    return F


class BuildFormScmFactory(object):
    def __new__(cls, active_chroots, package=None):
        return _get_build_form(active_chroots, PackageFormScm, package)


class BuildFormPyPIFactory(object):
    def __new__(cls, active_chroots, package=None):
        return _get_build_form(active_chroots, PackageFormPyPI, package)


class BuildFormRubyGemsFactory(object):
    def __new__(cls, active_chroots, package=None):
        return _get_build_form(active_chroots, PackageFormRubyGems, package)


class BuildFormDistGitFactory(object):
    def __new__(cls, active_chroots):
        return _get_build_form(active_chroots, PackageFormDistGit)


class BuildFormUploadFactory(object):
    def __new__(cls, active_chroots):
        form = _get_build_form(active_chroots, BaseForm)
        form.pkgs = FileField('srpm', validators=[
            FileRequired(),
            SrpmValidator()])
        return form


class BuildFormCustomFactory(object):
    def __new__(cls, active_chroots, package=None):
        return _get_build_form(active_chroots, PackageFormCustom, package)


class BuildFormDistGitSimpleFactory:
    """
    Transform DistGitSimple package form into build form
    """
    def __new__(cls, active_chroots, package=None):
        return _get_build_form(active_chroots, PackageFormDistGitSimple,
                                    package)

class BuildFormUrlFactory(object):
    def __new__(cls, active_chroots):
        form = _get_build_form(active_chroots, BaseForm)
        form.pkgs = wtforms.TextAreaField(
            "Pkgs",
            validators=[
                wtforms.validators.DataRequired(message="URLs to packages are required"),
                UrlListValidator(),
                UrlSrpmListValidator()],
            filters=[StringListFilter()])
        return form


class ModuleFormUploadFactory(BaseForm):
    modulemd = FileField("modulemd", validators=[
        FileRequired(),
        # @TODO Validate modulemd.yaml file
    ])

    create = wtforms.BooleanField("create", default=True, false_values=FALSE_VALUES)
    build = wtforms.BooleanField("build", default=True, false_values=FALSE_VALUES)


def get_module_build_form(*args, **kwargs):
    class ModuleBuildForm(BaseForm):
        modulemd = FileField("modulemd")
        scmurl = wtforms.StringField()
        branch = wtforms.StringField()

        distgit = DistGitSelectField()

    return ModuleBuildForm(*args, **kwargs)


class PagureIntegrationForm(BaseForm):
    repo_url = wtforms.StringField("repo_url", default='')
    api_key = wtforms.StringField("api_key", default='')

    def __init__(self, api_key=None, repo_url=None, *args, **kwargs):
        super(PagureIntegrationForm, self).__init__(*args, **kwargs)
        if api_key != None:
            self.api_key.data = api_key
        if repo_url != None:
            self.repo_url.data = repo_url


class ChrootForm(BaseForm):

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

    module_toggle = wtforms.StringField("Modules",
                                        validators=[ModuleEnableNameValidator()],
                                        filters=[StringWhiteCharactersFilter()]
                                        )

    with_opts = wtforms.StringField("With options")
    without_opts = wtforms.StringField("Without options")

    bootstrap = create_mock_bootstrap_field("chroot")
    bootstrap_image = create_mock_bootstrap_image_field()
    isolation = create_isolation_field("chroot")

    def validate(self, *args, **kwargs):  # pylint: disable=signature-differs
        """ We need to special-case custom_image configuration """
        result = super().validate(*args, **kwargs)
        if self.bootstrap.data != "custom_image":
            return result
        if not self.bootstrap_image.data:
            self.bootstrap_image.errors.append(
                "Custom image is selected, but not specified")
            return False
        return result


class CoprChrootExtend(BaseForm):
    extend = wtforms.StringField("Chroot name")
    expire = wtforms.StringField("Chroot name")
    ownername = wtforms.HiddenField("Owner name")
    projectname = wtforms.HiddenField("Project name")


class CoprLegalFlagForm(BaseForm):
    comment = wtforms.TextAreaField("Comment")


class PermissionsApplierFormFactory(object):

    @staticmethod
    def create_form_cls(permission=None):
        class F(BaseForm):
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
        class F(BaseForm):
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


class CoprForkFormFactory(object):
    @staticmethod
    def create_form_cls(copr, user, groups):
        class F(BaseForm):
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
    reset_fields = wtforms.StringField("Reset these fields to their defaults")


class SelectMultipleFieldNoValidation(wtforms.SelectMultipleField):
    """
    Otherwise choices are required and in some cases we don't know them beforehand
    """
    def pre_validate(self, form):
        pass


class PinnedCoprsForm(BaseForm):
    copr_ids = SelectMultipleFieldNoValidation(wtforms.IntegerField("Pinned Copr ID"))

    def __init__(self, owner, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.owner = owner

    def validate(self):
        super().validate()

        choices = [str(c.id) for c in ComplexLogic.get_coprs_pinnable_by_owner(self.owner)]
        if any([i and i not in choices for i in self.copr_ids.data]):
            self.copr_ids.errors.append("Unexpected value selected")
            return False

        limit = app.config["PINNED_PROJECTS_LIMIT"]
        if len(self.copr_ids.data) > limit:
            self.copr_ids.errors.append("Too many pinned projects. Limit is {}!".format(limit))
            return False

        if len(list(filter(None, self.copr_ids.data))) != len(set(filter(None, self.copr_ids.data))):
            self.copr_ids.errors.append("You can pin a particular project only once")
            return False

        return True


class VoteForCopr(BaseForm):
    """
    Form for upvoting and downvoting projects
    """
    upvote = wtforms.SubmitField("Upvote")
    downvote = wtforms.SubmitField("Downvote")
    reset = wtforms.SubmitField("Reset vote")


class AdminPlaygroundForm(BaseForm):
    playground = wtforms.BooleanField("Playground", false_values=FALSE_VALUES)


class AdminPlaygroundSearchForm(BaseForm):
    project = wtforms.StringField("Project")


class GroupUniqueNameValidator(object):

    def __init__(self, message=None):
        if not message:
            message = "Group with the alias '{}' already exists."
        self.message = message

    def __call__(self, form, field):
        if UsersLogic.group_alias_exists(field.data):
            raise wtforms.ValidationError(self.message.format(field.data))


class ActivateFasGroupForm(BaseForm):

    name = wtforms.StringField(
        validators=[
            wtforms.validators.Regexp(
                re.compile(r"^[\w.-]+$"),
                message="Name must contain only letters,"
                "digits, underscores, dashes and dots."),
            GroupUniqueNameValidator()
        ]
    )


class CreateModuleForm(BaseForm):
    builds = wtforms.FieldList(wtforms.StringField("Builds ID list"))
    packages = wtforms.FieldList(wtforms.StringField("Packages list"))
    components = wtforms.FieldList(
        wtforms.StringField("Components"),
        validators=[
            wtforms.validators.DataRequired("You must select some packages from this project")
        ])
    filter = wtforms.FieldList(wtforms.StringField("Package Filter"))
    api = wtforms.FieldList(wtforms.StringField("Module API"))
    profile_names = wtforms.FieldList(wtforms.StringField("Install Profiles"), min_entries=2)
    profile_pkgs = wtforms.FieldList(wtforms.FieldList(wtforms.StringField("Install Profiles")), min_entries=2)

    def __init__(self, copr=None, *args, **kwargs):
        self.copr = copr
        super(CreateModuleForm, self).__init__(*args, **kwargs)

    def validate(self):
        if not BaseForm.validate(self):
            return False

        # Profile names should be unique
        names = [x for x in self.profile_names.data if x]
        if len(set(names)) < len(names):
            self.profile_names.errors.append("Profile names must be unique")
            return False

        # WORKAROUND
        # profile_pkgs are somehow sorted so if I fill profile_name in the first box and
        # profile_pkgs in seconds box, it is sorted and validated correctly
        for i in range(0, len(self.profile_names.data)):
            # If profile name is not set, then there should not be any packages in this profile
            if not flask.request.form["profile_names-{}".format(i)]:
                if [j for j in range(0, len(self.profile_names)) if "profile_pkgs-{}-{}".format(i, j) in flask.request.form]:
                    self.profile_names.errors.append("Missing profile name")
                    return False
        return True


class ModuleRepo(BaseForm):
    owner = wtforms.StringField("Owner Name", validators=[wtforms.validators.DataRequired()])
    copr = wtforms.StringField("Copr Name", validators=[wtforms.validators.DataRequired()])
    name = wtforms.StringField("Name", validators=[wtforms.validators.DataRequired()])
    stream = wtforms.StringField("Stream", validators=[wtforms.validators.DataRequired()])
    version = wtforms.IntegerField("Version", validators=[wtforms.validators.DataRequired()])
    arch = wtforms.StringField("Arch", validators=[wtforms.validators.DataRequired()])
