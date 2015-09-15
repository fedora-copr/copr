import re
import urlparse

import flask
import wtforms
from flask_wtf.file import FileAllowed, FileRequired, FileField

from flask.ext import wtf

from coprs import constants
from coprs import helpers
from coprs import models
from coprs.logic import coprs_logic


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
        parsed = urlparse.urlparse(url)
        if not parsed.scheme.startswith("http"):
            return False
        if not parsed.netloc:
            return False
        return True


class UrlRepoListValidator(UrlListValidator):
    """ Allows also `repo://` schema"""
    def is_url(self, url):
        parsed = urlparse.urlparse(url)
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
            message = ("URLs must end with .src.rpm"
                       " ('{0}' doesn't seem to be a valid SRPM URL).")
        super(UrlSrpmListValidator, self).__init__(message)

    def is_url(self, url):
        parsed = urlparse.urlparse(url)
        if not parsed.path.endswith((".src.rpm", ".nosrc.rpm")):
            return False
        return True


class SrpmValidator(object):
    def __init__(self, message=None):
        if not message:
            message = "You can upload only .src.rpm and .nosrc.rpm files"
        self.message = message

    def __call__(self, form, field):
        filename = field.data.filename.lower()
        if not filename.endswith((".src.rpm", ".nosrc.rpm")):
            raise wtforms.ValidationError(self.message)


class CoprUniqueNameValidator(object):

    def __init__(self, message=None, owner=None):
        if not message:
            message = "You already have project named '{0}'."
        self.message = message
        if not owner:
            owner = flask.g.user
        self.owner = owner

    def __call__(self, form, field):
        existing = coprs_logic.CoprsLogic.exists_for_user(
            self.owner, field.data).first()

        if existing and str(existing.id) != form.id.data:
            raise wtforms.ValidationError(self.message.format(field.data))


class NameNotNumberValidator(object):

    def __init__(self, message=None, owner=None):
        if not message:
            message = "Project's name can not be just number."
        self.message = message

    def __call__(self, form, field):
        if field.data.isdigit():
            raise wtforms.ValidationError(self.message.format(field.data))


class EmailOrURL(object):

    def __init__(self, message=None, owner=None):
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
    def create_form_cls(mock_chroots=None, owner=None):
        class F(wtf.Form):
            # also use id here, to be able to find out whether user
            # is updating a copr if so, we don't want to shout
            # that name already exists
            id = wtforms.HiddenField()

            name = wtforms.StringField(
                "Name",
                validators=[
                    wtforms.validators.DataRequired(),
                    wtforms.validators.Regexp(
                        re.compile(r"^[\w.-]+$"),
                        message="Name must contain only letters,"
                        "digits, underscores, dashes and dots."),
                    CoprUniqueNameValidator(owner=owner),
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

            disable_createrepo = wtforms.BooleanField(default=False)
            build_enable_net = wtforms.BooleanField(default=True)

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
                    self._mock_chroots_error = "At least one chroot" \
                        " must be selected"
                    return False
                return True

            def validate_mock_chroots_not_empty(self):
                have_any = False
                for c in self.chroots_list:
                    if getattr(self, c).data:
                        have_any = True
                return have_any

        F.chroots_list = map(lambda x: x.name,
                             models.MockChroot.query.filter(
                                 models.MockChroot.is_active == True
                             ).all())
        F.chroots_list.sort()
        # sets of chroots according to how we should print them in columns
        F.chroots_sets = {}
        for ch in F.chroots_list:
            checkbox_default = False
            if mock_chroots and ch in map(lambda x: x.name,
                                          mock_chroots):
                checkbox_default = True

            setattr(F, ch, wtforms.BooleanField(ch, default=checkbox_default))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


class CoprDeleteForm(wtf.Form):
    verify = wtforms.TextField(
        "Confirm deleting by typing 'yes'",
        validators=[
            wtforms.validators.Required(),
            wtforms.validators.Regexp(
                r"^yes$",
                message="Type 'yes' - without the quotes, lowercase.")
        ])


class BuildFormFactory(object):
    @staticmethod
    def create_form_cls(active_chroots):
        class F(wtf.Form):
            @property
            def selected_chroots(self):
                selected = []
                for ch in self.chroots_list:
                    if getattr(self, ch).data:
                        selected.append(ch)
                return selected

            pkgs = wtforms.TextAreaField(
                "Pkgs",
                validators=[
                    wtforms.validators.DataRequired(message="URLs to packages are required"),
                    UrlListValidator(),
                    UrlSrpmListValidator()],
                filters=[StringListFilter()])

            memory_reqs = wtforms.IntegerField(
                "Memory requirements",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(
                        min=constants.MIN_BUILD_MEMORY,
                        max=constants.MAX_BUILD_MEMORY)],
                default=constants.DEFAULT_BUILD_MEMORY)

            timeout = wtforms.IntegerField(
                "Timeout",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(
                        min=constants.MIN_BUILD_TIMEOUT,
                        max=constants.MAX_BUILD_TIMEOUT)],
                default=constants.DEFAULT_BUILD_TIMEOUT)

            enable_net = wtforms.BooleanField()

        F.chroots_list = map(lambda x: x.name, active_chroots)
        F.chroots_list.sort()
        F.chroots_sets = {}
        for ch in F.chroots_list:
            setattr(F, ch, wtforms.BooleanField(ch, default=True))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


class BuildFormUploadFactory(object):
    @staticmethod
    def create_form_cls(active_chroots):
        class F(wtf.Form):
            @property
            def selected_chroots(self):
                selected = []
                for ch in self.chroots_list:
                    if getattr(self, ch).data:
                        selected.append(ch)
                return selected

            pkgs = FileField('srpm', validators=[
                FileRequired(),
                SrpmValidator()])

            memory_reqs = wtforms.IntegerField(
                "Memory requirements",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(
                        min=constants.MIN_BUILD_MEMORY,
                        max=constants.MAX_BUILD_MEMORY)],
                default=constants.DEFAULT_BUILD_MEMORY)

            timeout = wtforms.IntegerField(
                "Timeout",
                validators=[
                    wtforms.validators.Optional(),
                    wtforms.validators.NumberRange(
                        min=constants.MIN_BUILD_TIMEOUT,
                        max=constants.MAX_BUILD_TIMEOUT)],
                default=constants.DEFAULT_BUILD_TIMEOUT)

            enable_net = wtforms.BooleanField()

        F.chroots_list = map(lambda x: x.name, active_chroots)
        F.chroots_list.sort()
        F.chroots_sets = {}
        for ch in F.chroots_list:
            setattr(F, ch, wtforms.BooleanField(ch, default=True))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


class BuildFormRebuildFactory(object):
    @staticmethod
    def create_form_cls(active_chroots):
        class F(wtf.Form):
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

            enable_net = wtforms.BooleanField()

        F.chroots_list = map(lambda x: x.name, active_chroots)
        F.chroots_list.sort()
        F.chroots_sets = {}
        for ch in F.chroots_list:
            setattr(F, ch, wtforms.BooleanField(ch, default=True))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


class ChrootForm(wtf.Form):

    """
    Validator for editing chroots in project
    (adding packages to minimal chroot)
    """

    buildroot_pkgs = wtforms.TextField(
        "Packages")

    comps = FileField("comps_xml")


class CoprLegalFlagForm(wtf.Form):
    comment = wtforms.TextAreaField("Comment")


class PermissionsApplierFormFactory(object):

    @staticmethod
    def create_form_cls(permission=None):
        class F(wtf.Form):
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
                    filters=[ValueToPermissionNumberFilter()]))

        setattr(F, "copr_admin",
                wtforms.BooleanField(
                    default=admin_default,
                    filters=[ValueToPermissionNumberFilter()]))

        return F


class PermissionsFormFactory(object):

    """Creates a dynamic form for given set of copr permissions"""
    @staticmethod
    def create_form_cls(permissions):
        class F(wtf.Form):
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


class CoprModifyForm(wtf.Form):
    description = wtforms.TextAreaField('Description',
                                        validators=[wtforms.validators.Optional()])

    instructions = wtforms.TextAreaField('Instructions',
                                         validators=[wtforms.validators.Optional()])

    repos = wtforms.TextAreaField('Repos',
                                  validators=[UrlRepoListValidator(),
                                              wtforms.validators.Optional()],
                                  filters=[StringListFilter()])

    disable_createrepo = wtforms.BooleanField(validators=[wtforms.validators.Optional()])


class ModifyChrootForm(wtf.Form):
    buildroot_pkgs = wtforms.TextField('Additional packages to be always present in minimal buildroot')


class AdminPlaygroundForm(wtf.Form):
    playground = wtforms.BooleanField("Playground")


class AdminPlaygroundSearchForm(wtf.Form):
    project = wtforms.TextField("Project")
