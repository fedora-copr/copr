# coding: utf-8
from marshmallow import Schema, fields


class AllowedMethodSchema(Schema):
    method = fields.Str()
    doc = fields.Str()
    require_auth = fields.Bool()
    params = fields.List(fields.Str())


class MockChroot(Schema):
    pass


class CoprSchema(Schema):
    name = fields.Str(required=True)
    description = fields.Str()
    instructions = fields.Str()

    auto_createrepo = fields.Bool()
    build_enable_net = fields.Bool()
    last_modified = fields.DateTime()

    additional_repos = fields.List(fields.Str, dump_only=True, attribute="repos_list")
    # yum_repos  = fields.List()

    # used only for creation
    chroots_to_enable = fields.List(fields.Str, load_only=True)

    _keys_to_make_object = [
        "description",
        "instructions",
        "auto_createrepo"
    ]

    def make_object(self, data):
        """
        Create kwargs for CoprsLogic.add
        """
        kwargs = dict(
            name=data["name"].strip(),
            repos=" ".join(data.get("repos", [])),
            selected_chroots=data["chroots"],
        )
        for key in self._keys_to_make_object:
            if key in data:
                kwargs[key] = data[key]
        return kwargs


class BuildChrootSchema(Schema):
    # used only for presentation
    state = fields.Str()
    started_on = fields.Int()
    ended_on = fields.Int()
    git_hash = fields.Str()


class BuildSchema(Schema):

    id = fields.Int()
    pkgs = fields.Str()
    build_packages = fields.Str()
    pkg_version = fields.Str()

    repos_list = fields.List(fields.Str())
    repos = fields.Str()  # legacy

    submitted_on = fields.Int()
    started_on = fields.Int()
    ended_on = fields.Int()

    results = fields.Str()
    memory_reqs = fields.Int()
    timeout = fields.Int()

    enable_net = fields.Bool()

    source_type = fields.Int()
    source_json = fields.Str()

    # chroots = fields.List(fields.Nested(BuildChrootSchema))




