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


class CoprUniqueNameValidator(object):
    def __init__(self, message = None):
        if not message:
            message = 'You already have copr named "{0}".'
        self.message = message

    def __call__(self, form, field):
        existing = coprs_logic.CoprsLogic.exists_for_user(flask.g.user, field.data).first()

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

class ValueToPermissionNumberFilter(object):
    def __call__(self, value):
        if value:
            return helpers.PermissionEnum('request')
        return helpers.PermissionEnum('nothing')

class CoprFormFactory(object):
    @staticmethod
    def create_form_cls(mock_chroots=None):
        class F(wtf.Form):
            # also use id here, to be able to find out whether user is updating a copr
            # if so, we don't want to shout that name already exists
            id = wtf.HiddenField()
            name = wtf.TextField('Name',
                                 validators = [wtf.Required(),
                                 wtf.Regexp(re.compile(r'^[\w.-]+$'), message='Name must contain only letters, digits, underscores, dashes and dots.'),
                                 CoprUniqueNameValidator()])
            description = wtf.TextAreaField('Description')
            instructions = wtf.TextAreaField('Instructions')
            repos = wtf.TextAreaField('Repos',
                                      validators = [UrlListValidator()],
                                      filters = [StringListFilter()])
            initial_pkgs = wtf.TextAreaField('Initial packages to build',
                                             validators = [UrlListValidator()],
                                             filters = [StringListFilter()])

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
                    self._mock_chroots_error = 'At least one chroot must be selected'
                    return False
                return True

            def validate_mock_chroots_not_empty(self):
                have_any = False
                for c in self.chroots_list:
                    if getattr(self, c).data:
                        have_any = True
                return have_any

        F.chroots_list = map(lambda x: x.chroot_name, models.MockChroot.query.filter(models.MockChroot.is_active==True).all())
        F.chroots_list.sort()
        F.chroots_sets = {} # sets of chroots according to how we should print them in columns
        for ch in F.chroots_list:
            checkbox_default = False
            if mock_chroots and ch in map(lambda x:x.chroot_name, mock_chroots):
                checkbox_default = True
            setattr(F, ch, wtf.BooleanField(ch, default=checkbox_default))
            if ch[0] in F.chroots_sets:
                F.chroots_sets[ch[0]].append(ch)
            else:
                F.chroots_sets[ch[0]] = [ch]

        return F


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

        builder_default = False
        admin_default = False

        if permission:
            if permission.copr_builder != helpers.PermissionEnum('nothing'):
                builder_default = True
            if permission.copr_admin != helpers.PermissionEnum('nothing'):
                admin_default = True

        setattr(F, 'copr_builder', wtf.BooleanField(default = builder_default, filters = [ValueToPermissionNumberFilter()]))
        setattr(F, 'copr_admin', wtf.BooleanField(default = admin_default, filters = [ValueToPermissionNumberFilter()]))

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

            setattr(F, 'copr_builder_{0}'.format(perm.user.id), wtf.SelectField(choices = builder_choices, default = builder_default, coerce = int))
            setattr(F, 'copr_admin_{0}'.format(perm.user.id), wtf.SelectField(choices = admin_choices, default = admin_default, coerce = int))

        return F
