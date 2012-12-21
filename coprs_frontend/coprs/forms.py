import re
import urlparse

import flask

from flask.ext import wtf

from coprs import constants
from coprs import helpers
from coprs import models
from coprs.logic import coprs_logic

class UrlListValidator(object):
    def __init__(self, message = None):
        if not message:
            message = 'A list of URLs separated by whitespace characters is needed ("{0}" doesn\'t seem to be a URL).'
        self.message = message

    def __call__(self, form, field):
        urls = field.data.split()
        for u in urls:
            if not self.is_url(u):
                raise wtf.ValidationError(self.message.format(u))

    def is_url(self, url):
        parsed = urlparse.urlparse(url)
        is_url = True

        if not parsed.scheme.startswith('http'):
            is_url = False
        if not parsed.netloc:
            is_url = False

        return is_url

class AllowedArchesValidator(object):
    def __init__(self, message = None):
        if not message:
            message = '"{0}" is not an allowed architecture for "{1}".'
        self.message = message

    def __call__(self, form, field):
        arches = field.data
        for a in arches:
            if a not in constants.CHROOTS[form.release.data]:
                raise wtf.ValidationError(self.message.format(a))

class CoprUniqueNameValidator(object):
    def __init__(self, message = None):
        if not message:
            message = 'You already have copr named "{0}".'
        self.message = message

    def __call__(self, form, field):
        existing = coprs_logic.CoprsLogic.exists_for_current_user(flask.g.user, field.data).first()

        if existing and str(existing.id) != form.id.data:
            raise wtf.ValidationError(self.message.format(field.data))


class StringListFilter(object):
    def __call__(self, value):
        if not value:
            return ''
        # Replace every whitespace string with one newline
        # Formats ideally for html form filling, use replace('\n', ' ')
        # to get space-separated values or split() to get list
        result = value.strip()
        regex = re.compile(r'\s+')
        return regex.sub(lambda x: '\n', result)

class CoprForm(wtf.Form):
    # also use id here, to be able to find out whether user is updating a copr
    # if so, we don't want to shout that name already exists
    id = wtf.HiddenField()
    name = wtf.TextField('Name',
                         validators = [wtf.Required(),
                         wtf.Regexp(re.compile(r'^[\w-]+$'), message = 'Name must contain only letters, digits, underscores and dashes.'),
                         CoprUniqueNameValidator()])
    # choices must be list of tuples
    # => make list like [(fedora-18, fedora-18), ...]
    release = wtf.SelectField('Release', choices = [(x, x) for x in sorted(constants.CHROOTS)])
    arches = wtf.SelectMultipleField('Architectures',
                                     choices = [(x, x) for x in constants.DEFAULT_ARCHES],
                                     validators = [wtf.Required(), AllowedArchesValidator()])
    repos = wtf.TextAreaField('Repos',
                              validators = [UrlListValidator()],
                              filters = [StringListFilter()])
    initial_pkgs = wtf.TextAreaField('Initial packages to build',
                                     validators = [UrlListValidator()],
                                     filters = [StringListFilter()])

    @property
    def chroots(self):
        return ['{0}-{1}'.format(self.release.data, arch) for arch in self.arches.data ]

class BuildForm(wtf.Form):
    pkgs = wtf.TextAreaField('Pkgs',
                             validators = [wtf.Required(), UrlListValidator()],
                             filters = [StringListFilter()])
    memory_reqs = wtf.IntegerField('Memory requirements',
                                   validators = [wtf.NumberRange(min = constants.MIN_BUILD_MEMORY, max = constants.MAX_BUILD_MEMORY)],
                                   default = constants.DEFAULT_BUILD_MEMORY)
    timeout = wtf.IntegerField('Timeout',
                               validators = [wtf.NumberRange(min = constants.MIN_BUILD_TIMEOUT, max = constants.MAX_BUILD_TIMEOUT)],
                               default = constants.DEFAULT_BUILD_TIMEOUT)

class PermissionsApplierFormFactory(object):
    @staticmethod
    def create_form_cls(permission = None):
        class F(wtf.Form):
            pass

        approved_num = helpers.PermissionEnum.num('Approved')
        build_without = approved_num
        admin_without = approved_num

        if permission:
            if permission.copr_builder == approved_num:
                build_without = None

            if permission.copr_admin == approved_num:
                admin_without = None

        builder_choices = helpers.PermissionEnum.choices_list(build_without)
        admin_choices = helpers.PermissionEnum.choices_list(admin_without)

        builder_default = permission.copr_builder if permission else helpers.PermissionEnum.num('No Action')
        admin_default = permission.copr_admin if permission else helpers.PermissionEnum.num('No Action')

        setattr(F, 'copr_builder', wtf.SelectField('Copr Builder', choices = builder_choices, default = builder_default))
        setattr(F, 'copr_admin', wtf.SelectField('Copr Admin', choices = admin_choices, default = admin_default))

        return F

class DynamicPermissionsFormFactory(object):
    """Creates a dynamic form for given set of copr permissions"""
    @staticmethod
    def create_form_cls(permissions):
        class F(wtf.Form):
            pass

        for perm in permissions:
            copr_builder_default = False
            if perm.copr_builder == helpers.PermissionEnum.num('Approved'):
                copr_builder_default = True

            copr_admin_default = False
            if perm.copr_admin == helpers.PermissionEnum.num('Approved'):
                copr_admin_default = True

            setattr(F, 'copr_builder_{0}'.format(perm.user.id), wtf.BooleanField(default = copr_builder_default))
            setattr(F, 'copr_admin_{0}'.format(perm.user.id), wtf.BooleanField(default = copr_admin_default))

        return F
