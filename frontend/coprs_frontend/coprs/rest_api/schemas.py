# coding: utf-8

from collections.abc import Iterable
from marshmallow import Schema as _Schema, fields, ValidationError, validate
from six import string_types


loads_kwargs = {}
try:
    from marshmallow.utils import EXCLUDE
    loads_kwargs = {"unknown": EXCLUDE}
except ImportError:
    pass


class Schema(_Schema):
    # In marshmallow v3+ there's no data/errors attributes as it was
    # in v2.  So we need to have compat wrapper.

    def wrap_function(self, name, *args, **kwargs):
        super_object = super(Schema, self)
        super_result = getattr(super_object, name)(*args, **kwargs)
        if hasattr(super_result, 'data') and hasattr(super_result, 'errors'):
            # old marshmallow
            data = super_result.data
            if super_result.errors:
                exception = ValidationError(super_result.errors)
                exception.valid_data = data
                raise exception
            return data
        else:
            return super_result

    def dump(self, *args, **kwargs):
        return self.wrap_function('dump', *args, **kwargs)

    def loads(self, *args, **kwargs):
        kwargs.update(loads_kwargs)
        return self.wrap_function('loads', *args, **kwargs)

def validate_any(fn_list):
    """
    :param fn_list: list of callable functions, each takes one param
    :return: None if at least one validation function exists without exceptions
    :raises ValidationError: otherwise
    """
    def func(value):
        errors = []
        for fn in fn_list:
            try:
                fn(value)
            except ValidationError as err:
                errors.append(str(err))
            else:
                return
        else:
            errors.insert(0, u"At least one validator should accept given value:")
            raise ValidationError(errors)

    return func


class SpaceSeparatedList(fields.Field):
    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return []
        return value.split()

    def _deserialize(self, value, attr=None, data=None, **kwargs):
        if value is None:
            return ""
        elif not isinstance(value, Iterable) or isinstance(value, string_types):
            raise ValidationError("Value `{}` is not a list of strings"
                                  .format(value))
        else:
            return " ".join(value)


class BuiltPackages(fields.Field):
    """ stored in db as a string:
    "python3-marshmallow 2.0.0b5\npython-marshmallow 2.0.0b5"
    we would represent them as
    { name: "pkg", version: "pkg version" }
    we implement only the serialization, since field is read-only
    """
    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return []
        result = []
        try:
            for chunk in value.split("\n"):
                pkg, version = chunk.split()
                result.append({
                    "name": pkg,
                    "version": version
                })
        except:
            pass

        return result


class AllowedMethodSchema(Schema):
    method = fields.Str()
    doc = fields.Str()
    require_auth = fields.Bool()
    params = fields.List(fields.Str())


class MockChrootSchema(Schema):
    class Meta:
        fields = ("name", "os_release", "os_version", "arch", "is_active")
        ordered = True


class ProjectSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)

    owner = fields.Str(attribute="owner_name", dump_only=True)
    is_a_group_project = fields.Bool(dump_only=True)
    group = fields.Str(attribute="group_name", dump_only=True)

    description = fields.Str(allow_none=True)
    instructions = fields.Str(allow_none=True)
    homepage = fields.Url(allow_none=True)
    contact = fields.Str(validate=validate_any([
        validate.URL(),
        validate.Email(),
        validate.OneOf(["", None]),
    ]), allow_none=True)

    disable_createrepo = fields.Bool(allow_none=True)
    build_enable_net = fields.Bool(allow_none=True)
    last_modified = fields.DateTime(dump_only=True)

    repos = SpaceSeparatedList(allow_none=True)


class ProjectCreateSchema(ProjectSchema):
    name = fields.Str(
        required=True,
        validate=[
            validate.Regexp(
                r"^[a-zA-Z][\w.-]*$",
                error="Name must contain only letters,"
                      "digits, underscores, dashes and dots."
                      "And starts with letter"),
        ])
    group = fields.Str(load_only=True, allow_none=True)
    chroots = SpaceSeparatedList(load_only=True, default=list)


# todo: rename to ProjectChrootSchema
class CoprChrootSchema(Schema):

    buildroot_pkgs = SpaceSeparatedList()
    name = fields.Str(dump_only=True)

    comps = fields.Str(allow_none=True)
    comps_name = fields.Str(allow_none=True)
    comps_len = fields.Int(dump_only=True)


class CoprChrootCreateSchema(CoprChrootSchema):
    name = fields.Str(required=True)


class BuildTaskSchema(Schema):
    # used only for presentation
    state = fields.Str()
    started_on = fields.Int(dump_only=True)
    ended_on = fields.Int(dump_only=True)
    git_hash = fields.Str(dump_only=True)
    chroot_name = fields.Str(dump_only=True, attribute="name")
    build_id = fields.Int(dump_only=True)

    result_dir_url = fields.Str(dump_only=True)


class BuildSchema(Schema):

    id = fields.Int(dump_only=True)
    state = fields.Str()

    submitter = fields.Str(dump_only=True, attribute="user_name")

    built_packages = BuiltPackages(dump_only=True)
    package_version = fields.Str(dump_only=True, attribute="pkg_version")
    package_name = fields.Str(dump_only=True)

    repos = SpaceSeparatedList(dump_only=True)

    submitted_on = fields.Int(dump_only=True)

    # timeout = fields.Int(dump_only=True)  # currently has no use
    enable_net = fields.Bool(dump_only=True)

    source_type = fields.Str(dump_only=True, attribute="source_type_text")
    source_metadata = fields.Raw(dump_only=True)


class BuildCreateSchema(BuildSchema):
    project_id = fields.Int(required=True)
    chroots = fields.List(fields.Str())
    enable_net = fields.Bool()

    state = fields.Str(dump_only=True)


class BuildCreateFromUrlSchema(BuildCreateSchema):
    srpm_url = fields.Url(required=True, validate=lambda u: u.startswith("http"))
