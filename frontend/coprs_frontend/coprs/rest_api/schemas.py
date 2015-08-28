# coding: utf-8

from collections import Iterable
from marshmallow import Schema, fields


class SpaceSeparatedList(fields.Field):
    def _serialize(self, value, attr, obj):
        if value is None:
            return []
        return value.split()

    def _deserialize(self, value):
        if value is None or not isinstance(value, Iterable):
            return ""
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
    id = fields.Int()
    name = fields.Str(required=True)

    owner = fields.Str(attribute="owner_name", dump_only=True)
    description = fields.Str()
    instructions = fields.Str()
    homepage = fields.Str()
    contact = fields.Str()

    auto_createrepo = fields.Bool()
    build_enable_net = fields.Bool()
    last_modified = fields.DateTime()

    #additional_repos = fields.List(fields.Str(), attribute="repos_list")
    repos = SpaceSeparatedList()

    # used only for creation
    chroots = fields.List(fields.Str(), load_only=True)


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


class BuildSchema(Schema):

    id = fields.Int(dump_only=True)
    state = fields.Str()

    pkgs = fields.Str(dump_only=True)
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
