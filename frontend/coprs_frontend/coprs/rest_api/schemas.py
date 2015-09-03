# coding: utf-8

from collections import Iterable
from marshmallow import Schema, fields
from marshmallow import Schema, fields, validates_schema, ValidationError, validate


def validate_any(fn_list):
    """
    :param fn_list: list of callable functions, each takes one param
    :return: None if at least one validation function exists without exceptions
    :raises ValidationError: otherwise
    """
    def func(value):
        # import ipdb; ipdb.set_trace()
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
    def _serialize(self, value, attr, obj):
        if value is None:
            return []
        return value.split()

    def _deserialize(self, value):
        if value is None:
            return ""
        elif not isinstance(value, Iterable) or isinstance(value, basestring):
            raise ValidationError("Value `{}` is not a list of strings"
                                  .format(value))
        else:
            return " ".join(value)


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
    chroots = SpaceSeparatedList(load_only=True, default=list)


class CoprChrootSchema(Schema):

    buildroot_pkgs = SpaceSeparatedList()
    name = fields.Str(dump_only=True)

    comps = fields.Str(allow_none=True)
    comps_name = fields.Str(allow_none=True)
    comps_len = fields.Int(dump_only=True)


class CoprChrootCreateSchema(CoprChrootSchema):
    name = fields.Str(required=True)


class BuildChrootSchema(Schema):
    # used only for presentation
    state = fields.Str()
    started_on = fields.Int(dump_only=True)
    ended_on = fields.Int(dump_only=True)
    git_hash = fields.Str(dump_only=True)
    name = fields.Str(dump_only=True)

    result_dir_url = fields.Str(dump_only=True)


class BuildSchema(Schema):

    id = fields.Int(dump_only=True)
    state = fields.Str()

    build_packages = fields.Str(dump_only=True)
    pkg_version = fields.Str(dump_only=True)

    repos = SpaceSeparatedList(dump_only=True)

    submitted_on = fields.Int(dump_only=True)
    started_on = fields.Int(dump_only=True)
    ended_on = fields.Int(dump_only=True)

    results = fields.Str(dump_only=True)

    timeout = fields.Int(dump_only=True)

    enable_net = fields.Bool(dump_only=True)

    source_type = fields.Int(dump_only=True)
    source_json = fields.Str(dump_only=True)


class BuildCreateSchema(BuildSchema):
    project_id = fields.Int(required=True)
    chroots = fields.List(fields.Str())
    enable_net = fields.Bool()


class BuildCreateFromUrlSchema(BuildCreateSchema):
    srpm_url = fields.Url(required=True, validate=lambda u: u.startswith("http"))
