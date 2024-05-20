# pylint: disable=missing-class-docstring, too-many-instance-attributes
# pylint: disable=unused-private-member

"""
File for schemas, models and data validation for our API

Sometime in the future, we can maybe drop some schemas and/or their generation and
generate them from SQLAlchemy models:
https://github.com/python-restx/flask-restx/pull/493/files

Things used for the input/output:
  - *_schema - describes our output schemas
  - *_model  - basically a pair schema and its name
"""


# dataclasses are written that way we can easily switch to marshmallow/pydantic
# as flask-restx docs suggests if needed
# look to https://github.com/fedora-copr/copr/issues/3031 for more


# TODO: in case we will use marshmallow/pydantic, we should share these schemas
#  somewhere (in copr common?) - CLI, frontend and backend (and maybe something else)
#  shares these data with each other


from dataclasses import dataclass, fields, asdict, MISSING
from typing import Any

from flask_restx.fields import String, List, Integer, Boolean, Nested, Raw

from coprs.views.apiv3_ns import api
from coprs.views.apiv3_ns.schema import fields as schema_fields
from coprs.views.apiv3_ns.schema.fields import (
    scm_type,
    mock_chroot,
    additional_repos,
    clone,
    id_field,
    url,
    Url,
)


@dataclass
class Schema:
    """
    Creates schemas/models for marshalling in flask-restx (and for data validation
     in future?). Fields are automatically taken from fields.py file if the name
     matches in Schema dataclass attribute and fields.py attribute, otherwise
     you have to specify the attribute value directly or map the naming
     in `unicorn_fields`.

    Usage:
        class SomeSchema(Schema):
            # if `some_attribute` is present in `fields.py` its value is used
            some_attribute: String

            # if e.g. attribute in `fields.py` has name `weird_attribute` and for some
            # reason you want to use `in_unicorn_map` here but still use the value
            # specified in `fields.py`, add into `unicorn_fields` map this:
            # "in_unicorn_map": "weird_attribute"
            in_unicorn_map: String

            # if `not_in_fields` is not in `fields.py` you have to specify its value
            not_in_fields: String = String(some definition ...)
    """

    @classmethod
    def schema_attrs_from_fields(cls) -> dict[str, Any]:
        """
        Get schema attributes for schema class according to its defined attributes.
         Attributes are taken from field file and the names should match.

        Returns:
            Schema for schema class
        """
        result_schema = {}
        for attr in fields(cls):
            if attr.default is MISSING:
                result_schema[attr.name] = clone(getattr(schema_fields, attr.name))
            else:
                result_schema[attr.name] = attr.default

        return result_schema

    @staticmethod
    def _should_be_item_candidate_to_delete(key: str, value: Any) -> bool:
        return (key.startswith("_") or not isinstance(value, Raw)) or (
            # masking feature is missing in marshaling
            hasattr(value, "mask") and value.mask
        )

    @classmethod
    def _convert_schema_class_dict_to_schema(cls, d: dict) -> dict:
        """
        Returns the same dictionary that was passed as param, doesn't create copy of it.
        """
        # if in fields.py file is attribute that has different name
        # than model, add it to `unicorn_fields` like
        # "field_name_in_fields.py": "what_you_want_to_name_it"
        unicorn_fields = {
            "id_field": "id",
        }
        # pylint: disable-next=consider-using-dict-items
        for field_to_rename in unicorn_fields:
            if field_to_rename in d:
                d[unicorn_fields[field_to_rename]] = d[field_to_rename]
                d.pop(field_to_rename)

        keys_to_delete = []
        for key, value in d.items():
            if cls._should_be_item_candidate_to_delete(key, value):
                keys_to_delete.append(key)

        for key_to_delete in keys_to_delete:
            d.pop(key_to_delete)

        return d

    @classmethod
    def get_cls(cls):
        """
        Get instance of schema class.
        """
        schema_dict = cls.schema_attrs_from_fields()
        return cls(**schema_dict)

    def public_fields(self):
        """
        Get all fields, private fields excluded
        """
        result = []
        for field in fields(self):
            if not field.name.startswith("_"):
                result.append(field)

        return result

    def schema(self):
        """
        Get schema dictionary with properly named key values (applies `unicorn_fields`).
         Returns dynamic print of dataclass in dictionary.
        """
        return self._convert_schema_class_dict_to_schema(asdict(self))

    def model(self):
        """
        Get Flask-restx model for the schema class.
        """
        return api.model(self.__class__.__name__, self.schema())


class InputSchema(Schema):
    """
    Creates input schemas for flask-restx (and for data validation in future?).
    """

    @property
    def required_attrs(self) -> list:
        """
        Specify required attributes in model in these methods if needed.

        Specify this property in subclass with required attributes. If no attribute
         is required, then don;t specify this property in subclass.

        In case every attribute is required in input schema, you have two options:
        A):
            Specify every attribute in required_attrs property.
        B):
            Define `__all_required` attribute in input schema and set it to `True`.
        """
        return []

    def _do_require_attrs(self):
        change_this_args_as_required = self.required_attrs
        if getattr(self, f"_{self.__class__.__name__}__all_required", False):
            change_this_args_as_required = [
                getattr(self, field.name) for field in self.public_fields()
            ]

        for field in change_this_args_as_required:
            field.required = True

    def input_model(self):
        """
        Returns an input model (input to @ns.expect()) with properly set required
         parameters.
        """
        self._do_require_attrs()
        return api.model(self.__class__.__name__, self.schema())


@dataclass
class ParamsSchema(InputSchema):
    """
    Creates argument documentation for api_foo_ns.docs decorator that passes
     documentation directly to Swagger UI.

    Do not use Argument class from flask-restx for generating documentation, it will
     be deprecated with parsers.
    """

    def params_schema(self) -> dict:
        """
        Returns parameters documentation that expands or overwrites default parameter
         documentation taken from api_foo_ns.route. Documentation is a dictionary
         in specific structure to match Swagger UI schema.
        """
        super()._do_require_attrs()
        schema = {}
        for field in self.public_fields():
            attr = getattr(self, field.name)
            schema[field.name] = attr.schema()

            keys_to_delete = []
            for key, val in schema[field.name].items():
                if val is None:
                    keys_to_delete.append(key)

            for key in keys_to_delete:
                schema[field.name].pop(key)

            if attr.required:
                schema[field.name] |= {"required": True}

        return schema


@dataclass
class PaginationMeta(ParamsSchema):
    limit: Integer
    offset: Integer
    order: String
    order_type: String


_pagination_meta_model = PaginationMeta.get_cls().model()


@dataclass
class Pagination(Schema):
    """
    Pagination items can be basically anything (any schema) so specify a model to
     `items` like this: build_pagination_model = Pagination(items=build_model).model()
    """

    items: Any = None
    meta: Nested = Nested(_pagination_meta_model)

    def model(self):
        if self.items is None:
            raise KeyError(
                "No items are defined in Pagination. Perhaps you forgot to"
                " specify it when creating Pagination instance?"
            )

        return super().model()


@dataclass
class _ProjectChrootFields:
    additional_repos: List
    additional_packages: List
    additional_modules: List
    with_opts: List
    without_opts: List
    isolation: String


@dataclass
class ProjectChroot(_ProjectChrootFields, Schema):
    mock_chroot: String
    ownername: String
    projectname: String
    comps_name: String
    delete_after_days: Integer


@dataclass
class ProjectChrootGet(ParamsSchema):
    ownername: String
    projectname: String
    chrootname: String = mock_chroot

    __all_required: bool = True


@dataclass
class Repo(Schema):
    baseurl: Url
    module_hotfixes: Boolean
    priority: Integer
    id_field: String = String(example="copr_base")
    name: String = String(example="Copr repository")


_repo_model = Repo.get_cls().model()


@dataclass
class ProjectChrootBuildConfig(_ProjectChrootFields, Schema):
    chroot: String
    enable_net: Boolean
    repos: List = List(Nested(_repo_model))


@dataclass
class _SourceDictScmFields:
    clone_url: String
    committish: String
    spec: String
    subdirectory: String


@dataclass
class SourceDictScm(_SourceDictScmFields, Schema):
    source_build_method: String
    type: String = scm_type


@dataclass
class SourceDictPyPI(Schema):
    pypi_package_name: String
    pypi_package_version: String
    spec_generator: String
    spec_template: String
    python_versions: List


@dataclass
class SourcePackage(Schema):
    name: String
    url: String
    version: String


_source_package_model = SourcePackage.get_cls().model()


@dataclass
class Build(Schema):
    chroots: List
    ended_on: Integer
    id_field: Integer
    is_background: Boolean
    ownername: String
    project_dirname: String
    projectname: String
    repo_url: Url
    started_on: Integer
    state: String
    submitted_on: Integer
    submitter: String
    source_package: Nested = Nested(_source_package_model)


_build_model = Build.get_cls().model()


@dataclass
class PackageBuilds(Schema):
    latest: Nested = Nested(_build_model, allow_null=True)
    latest_succeeded: Nested = Nested(_build_model, allow_null=True)


_package_builds_model = PackageBuilds().model()


@dataclass
class Package(Schema):
    id_field: Integer
    name: String
    ownername: String
    projectname: String
    source_type: String
    source_dict: Raw
    auto_rebuild: Boolean
    builds: Nested = Nested(_package_builds_model)


@dataclass
class PackageGet(ParamsSchema):
    ownername: String
    projectname: String
    packagename: String
    with_latest_build: Boolean
    with_latest_succeeded_build: Boolean

    @property
    def required_attrs(self) -> list:
        return [self.ownername, self.projectname, self.packagename]


@dataclass
class BasePackage(InputSchema):
    max_builds: Integer
    timeout: Integer
    webhook_rebuild: Boolean
    packagename: String


@dataclass
class PackageAdd(_SourceDictScmFields, SourceDictPyPI, BasePackage, InputSchema):
    # rest of SCM
    scm_type: String

    # Rubygems
    gem_name: String

    # Custom
    script: String
    builddeps: String
    resultdir: String
    chroot: String

    source_build_method: String



@dataclass
class _ProjectFields:
    homepage: Url
    contact: String
    description: String
    instructions: String
    devel_mode: Boolean
    unlisted_on_hp: Boolean
    auto_prune: Boolean
    enable_net: Boolean
    bootstrap: String
    isolation: String
    module_hotfixes: Boolean
    appstream: Boolean
    packit_forge_projects_allowed: String
    follow_fedora_branching: Boolean
    repo_priority: Integer


@dataclass
class _ProjectGetAddFields:
    name: String
    persistent: Boolean
    additional_repos: List


@dataclass
class Project(_ProjectFields, _ProjectGetAddFields, Schema):
    id_field: Integer
    ownername: String
    full_name: String
    chroot_repos: Raw


@dataclass
class _ProjectAddEditFields:
    chroots: List
    bootstrap_image: String
    multilib: Boolean
    fedora_review: Boolean
    runtime_dependencies: String


@dataclass
class ProjectAdd(
    _ProjectFields, _ProjectGetAddFields, _ProjectAddEditFields, InputSchema
):
    ...


@dataclass
class ProjectEdit(_ProjectFields, _ProjectAddEditFields, InputSchema):
    # TODO: fix inconsistency - additional_repos <-> repos
    repos: String = additional_repos


@dataclass
class ProjectFork(InputSchema):
    name: String
    ownername: String
    confirm: Boolean


@dataclass
class ProjectDelete(InputSchema):
    verify: Boolean


@dataclass
class FullnameSchema(ParamsSchema):
    ownername: String
    projectname: String

    __all_required: bool = True


@dataclass
class CanBuildParams(FullnameSchema):
    who: String = String(example="user123")

    __all_required: bool = True


@dataclass
class CanBuildSchema(CanBuildParams):
    can_build_in: Boolean = Boolean(example=True)


@dataclass
class ProjectParamsSchema(ParamsSchema):
    ownername: String
    exist_ok: Boolean


@dataclass
class BuildChroot(Schema):
    started_on: Integer
    ended_on: Integer
    state: String
    name: String = mock_chroot
    result_url: Url = url


@dataclass
class BuildChrootParams(ParamsSchema):
    build_id: Integer = id_field
    chrootname: String = mock_chroot

    __all_required: bool = True


@dataclass
class BuildChrootConfig(Schema):
    additional_repos: List
    additional_packages: List
    with_opts: List
    without_opts: List
    enable_net: Boolean
    is_background: Boolean
    memory_limit: Integer
    timeout: Integer
    bootstrap: String
    bootstrap_image: String
    repos: List = List(Nested(_repo_model))


@dataclass
class Nevra(Schema):
    arch: String
    epoch: Integer
    release: String
    version: String
    name: String = String(description="Package name")


_nevra_model = Nevra.get_cls().model()


@dataclass
class NevraPackages(Schema):
    packages: List = List(Nested(_nevra_model))


@dataclass
class ModuleBuild(Schema):
    nsv: String


@dataclass
class WebhookSecret(Schema):
    id_field: String
    name: String
    ownername: String
    full_name: String
    webhook_secret: String


@dataclass
class ModuleAdd(InputSchema):
    modulemd: String
    distgit: String
    scmurl: String


@dataclass
class _ModulePackage(Schema):
    name: String
    # inconsistent keys in chroots dict, impossible with flask-restx to do
    chroots: Raw = Raw(
        description="Chroots and their states",
        example={"fedora-rawhide-i386": {"state": "waiting", "status": 1, "build_id": 1}},
    )


_module_package_model = _ModulePackage.get_cls().model()


@dataclass
class Monitor(Schema):
    message: String = String(example="Project monitor request successful")
    output: String = String(example="ok")
    packages: List = List(Nested(_module_package_model))


@dataclass
class SourceChroot(Schema):
    state: String
    result_url: Url


@dataclass
class SourceBuildConfig(Schema):
    source_type: String
    source_dict: Raw
    memory_limit: Integer
    timeout: Integer
    is_background: Boolean


@dataclass
class ListBuild(ParamsSchema):
    ownername: String
    projectname: String
    packagename: String
    status: String

    @property
    def required_attrs(self) -> list:
        return [self.ownername, self.projectname]


@dataclass
class _GenericBuildOptions:
    chroot_names: List
    background: Boolean
    timeout: Integer
    bootstrap: String
    isolation: String
    after_build_id: Integer
    with_build_id: Integer
    packit_forge_project: String
    enable_net: Boolean


@dataclass
class _BuildDataCommon:
    ownername: String
    projectname: String


@dataclass
class CreateBuildUrl(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    project_dirname: String
    pkgs: List = List(
        Url,
        description="List of urls to build from",
        example=["https://example.com/some.src.rpm"],
    )


@dataclass
class CreateBuildUpload(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    project_dirname: String
    pkgs: List = List(Raw, description="application/x-rpm files to build from")


@dataclass
class CreateBuildSCM(_BuildDataCommon, _GenericBuildOptions, _SourceDictScmFields, InputSchema):
    project_dirname: String
    scm_type: String
    source_build_method: String


@dataclass
class CreateBuildDistGit(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    distgit: String
    namespace: String
    package_name: String
    committish: String
    project_dirname: String


@dataclass
class CreateBuildPyPI(_BuildDataCommon, _GenericBuildOptions, SourceDictPyPI, InputSchema):
    project_dirname: String


@dataclass
class CreateBuildRubyGems(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    project_dirname: String
    gem_name: String


@dataclass
class CreateBuildCustom(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    script: String
    chroot: String
    builddeps: String
    resultdir: String
    project_dirname: String
    repos: List = List(Nested(_repo_model))


@dataclass
class DeleteBuilds(InputSchema):
    builds: List = List(Integer, description="List of build ids to delete")



# OUTPUT MODELS
project_chroot_model = ProjectChroot.get_cls().model()
project_chroot_build_config_model = ProjectChrootBuildConfig.get_cls().model()
source_dict_scm_model = SourceDictScm.get_cls().model()
source_dict_pypi_model = SourceDictPyPI.get_cls().model()
package_model = Package.get_cls().model()
project_model = Project.get_cls().model()
build_chroot_model = BuildChroot.get_cls().model()
build_chroot_config_model = BuildChrootConfig.get_cls().model()
nevra_packages_model = NevraPackages.get_cls().model()
module_build_model = ModuleBuild.get_cls().model()
webhook_secret_model = WebhookSecret.get_cls().model()
monitor_model = Monitor.get_cls().model()
can_build_in_model = CanBuildSchema.get_cls().model()
source_chroot_model = SourceChroot.get_cls().model()
source_build_config_model = SourceBuildConfig.get_cls().model()
list_build_model = DeleteBuilds.get_cls().model()

pagination_project_model = Pagination(items=List(Nested(project_model))).model()
pagination_build_chroot_model = Pagination(items=List(Nested(build_chroot_model))).model()
pagination_package_model = Pagination(items=List(Nested(package_model))).model()
pagination_build_model = Pagination(items=List(Nested(_build_model))).model()

source_package_model = _source_package_model
build_model = _build_model
package_builds_model = _package_builds_model
repo_model = _repo_model


# INPUT MODELS
package_add_input_model = PackageAdd.get_cls().input_model()
package_edit_input_model = package_add_input_model
base_package_input_model = BasePackage.get_cls().input_model()

project_add_input_model = ProjectAdd.get_cls().input_model()
project_edit_input_model = ProjectEdit.get_cls().input_model()
project_fork_input_model = ProjectFork.get_cls().input_model()
project_delete_input_model = ProjectDelete.get_cls().input_model()
module_add_input_model = ModuleAdd.get_cls().input_model()

create_build_url_input_model = CreateBuildUrl.get_cls().input_model()
create_build_upload_input_model = CreateBuildUpload.get_cls().input_model()
create_build_scm_input_model = CreateBuildSCM.get_cls().input_model()
create_build_distgit_input_model = CreateBuildDistGit.get_cls().input_model()
create_build_pypi_input_model = CreateBuildPyPI.get_cls().input_model()
create_build_rubygems_input_model = CreateBuildRubyGems.get_cls().input_model()
create_build_custom_input_model = CreateBuildCustom.get_cls().input_model()
delete_builds_input_model = DeleteBuilds.get_cls().input_model()


# PARAMETER SCHEMAS
package_get_params = PackageGet.get_cls().params_schema()
package_get_list_params = package_get_params.copy()
package_get_list_params.pop("packagename")
project_chroot_get_params = ProjectChrootGet.get_cls().params_schema()
fullname_params = FullnameSchema.get_cls().params_schema()
project_params = ProjectParamsSchema.get_cls().params_schema()
pagination_params = PaginationMeta.get_cls().params_schema()
build_chroot_params = BuildChrootParams.get_cls().params_schema()
build_id_params = {"build_id": build_chroot_params["build_id"]}
can_build_params = CanBuildParams.get_cls().params_schema()
list_build_params = ListBuild.get_cls().params_schema()
