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


class BuildSchema(Schema):

    id = fields.Int()
    state = fields.Str()

    pkgs = fields.Str()
    build_packages = fields.Str()
    pkg_version = fields.Str()

    repos_list = fields.List(fields.Str())
    repos = fields.Str()  # todo: replace with SpaceSeparatedList

    submitted_on = fields.Int()
    started_on = fields.Int()
    ended_on = fields.Int()

    results = fields.Str()
    timeout = fields.Int()

    enable_net = fields.Bool()

    source_type = fields.Int()
    source_json = fields.Str()

    # owner = fields.Function(lambda b: b.copr.owner.username, dump_only=True)
