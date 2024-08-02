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


from dataclasses import dataclass, fields as dataclasses_fields, asdict
from typing import Any

from flask_restx.fields import String, List, Integer, Boolean, Nested, Raw

from coprs.views.apiv3_ns import api
from coprs.views.apiv3_ns.schema import fields
from coprs.views.apiv3_ns.schema.fields import (
    scm_type,
    mock_chroot,
    additional_repos,
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
        schema = {attr.name: attr.default for attr in dataclasses_fields(cls)}
        return cls(**schema)

    def public_fields(self):
        """
        Get all fields, private fields excluded
        """
        result = []
        for field in dataclasses_fields(self):
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
    limit: Integer = fields.limit
    offset: Integer = fields.offset
    order: String = fields.order
    order_type: String = fields.order_type


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
    additional_repos: List = fields.additional_repos
    additional_packages: List = fields.additional_packages
    additional_modules: List = fields.additional_modules
    with_opts: List = fields.with_opts
    without_opts: List = fields.without_opts
    isolation: String = fields.isolation


@dataclass
class ProjectChroot(_ProjectChrootFields, Schema):
    mock_chroot: String = fields.mock_chroot
    ownername: String = fields.ownername
    projectname: String = fields.projectname
    comps_name: String = fields.comps_name
    delete_after_days: Integer = fields.delete_after_days


@dataclass
class ProjectChrootGet(ParamsSchema):
    ownername: String = fields.ownername
    projectname: String = fields.projectname
    chrootname: String = mock_chroot

    __all_required: bool = True


@dataclass
class Repo(Schema):
    baseurl: Url = fields.baseurl
    module_hotfixes: Boolean = fields.module_hotfixes
    priority: Integer = fields.priority
    id_field: String = String(example="copr_base")
    name: String = String(example="Copr repository")


_repo_model = Repo.get_cls().model()


@dataclass
class ProjectChrootBuildConfig(_ProjectChrootFields, Schema):
    chroot: String = fields.chroot
    enable_net: Boolean = fields.enable_net
    repos: List = List(Nested(_repo_model))


@dataclass
class _SourceDictScmFields:
    clone_url: String = fields.clone_url
    committish: String = fields.committish
    spec: String = fields.spec
    subdirectory: String = fields.subdirectory


@dataclass
class SourceDictScm(_SourceDictScmFields, Schema):
    source_build_method: String = fields.source_build_method
    type: String = scm_type


@dataclass
class SourceDictPyPI(Schema):
    pypi_package_name: String = fields.pypi_package_name
    pypi_package_version: String = fields.pypi_package_version
    spec_generator: String = fields.spec_generator
    spec_template: String = fields.spec_template
    python_versions: List = fields.python_versions


@dataclass
class SourcePackage(Schema):
    name: String = fields.name
    url: String = fields.url
    version: String = fields.version


_source_package_model = SourcePackage.get_cls().model()


@dataclass
class Build(Schema):
    chroots: List = fields.chroots
    ended_on: Integer = fields.ended_on
    id_field: Integer = fields.id_field
    is_background: Boolean = fields.is_background
    ownername: String = fields.ownername
    project_dirname: String = fields.project_dirname
    projectname: String = fields.projectname
    repo_url: Url = fields.repo_url
    started_on: Integer = fields.started_on
    state: String = fields.state
    submitted_on: Integer = fields.submitted_on
    submitter: String = fields.submitter
    source_package: Nested = Nested(_source_package_model)


_build_model = Build.get_cls().model()


@dataclass
class PackageBuilds(Schema):
    latest: Nested = Nested(_build_model, allow_null=True)
    latest_succeeded: Nested = Nested(_build_model, allow_null=True)


_package_builds_model = PackageBuilds().model()


@dataclass
class Package(Schema):
    id_field: Integer = fields.id_field
    name: String = fields.packagename
    ownername: String = fields.ownername
    projectname: String = fields.projectname
    source_type: String = fields.source_type
    source_dict: Raw = fields.source_dict
    auto_rebuild: Boolean = fields.auto_rebuild
    builds: Nested = Nested(_package_builds_model)


@dataclass
class PackageGet(ParamsSchema):
    ownername: String = fields.ownername
    projectname: String = fields.projectname
    packagename: String = fields.packagename
    with_latest_build: Boolean = fields.with_latest_build
    with_latest_succeeded_build: Boolean = fields.with_latest_succeeded_build

    @property
    def required_attrs(self) -> list:
        return [self.ownername, self.projectname, self.packagename]


@dataclass
class BasePackage(InputSchema):
    max_builds: Integer = fields.max_builds
    timeout: Integer = fields.timeout
    webhook_rebuild: Boolean = fields.webhook_rebuild
    packagename: String = fields.packagename


@dataclass
class PackageAdd(_SourceDictScmFields, SourceDictPyPI, BasePackage, InputSchema):
    # rest of SCM
    scm_type: String = fields.scm_type

    # Rubygems
    gem_name: String = fields.gem_name

    # Custom
    script: String = fields.script
    builddeps: String = fields.builddeps
    resultdir: String = fields.resultdir
    chroot: String = fields.chroot

    source_build_method: String = fields.source_build_method


@dataclass
class _ProjectFields:
    homepage: Url = fields.homepage
    contact: String = fields.contact
    description: String = fields.description
    instructions: String = fields.instructions
    devel_mode: Boolean = fields.devel_mode
    unlisted_on_hp: Boolean = fields.unlisted_on_hp
    auto_prune: Boolean = fields.auto_prune
    enable_net: Boolean = fields.enable_net
    bootstrap: String = fields.bootstrap
    isolation: String = fields.isolation
    module_hotfixes: Boolean = fields.module_hotfixes
    appstream: Boolean = fields.appstream
    packit_forge_projects_allowed: String = fields.packit_forge_projects_allowed
    follow_fedora_branching: Boolean = fields.follow_fedora_branching
    repo_priority: Integer = fields.repo_priority


@dataclass
class _ProjectGetAddFields:
    name: String = fields.name
    persistent: Boolean = fields.persistent
    additional_repos: List = fields.additional_repos


@dataclass
class Project(_ProjectFields, _ProjectGetAddFields, Schema):
    id_field: Integer = fields.id_field
    ownername: String = fields.ownername
    full_name: String = fields.full_name
    chroot_repos: Raw = fields.chroot_repos


@dataclass
class _ProjectAddEditFields:
    chroots: List = fields.chroots
    bootstrap_image: String = fields.bootstrap_image
    multilib: Boolean = fields.multilib
    fedora_review: Boolean = fields.fedora_review
    runtime_dependencies: String = fields.runtime_dependencies


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
    name: String = fields.name
    ownername: String = fields.ownername
    confirm: Boolean = fields.confirm


@dataclass
class ProjectDelete(InputSchema):
    verify: Boolean = fields.verify


@dataclass
class FullnameSchema(ParamsSchema):
    ownername: String = fields.ownername
    projectname: String = fields.projectname

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
    ownername: String = fields.ownername
    exist_ok: Boolean = fields.exist_ok


@dataclass
class BuildChroot(Schema):
    started_on: Integer = fields.started_on
    ended_on: Integer = fields.ended_on
    state: String = fields.state
    name: String = mock_chroot
    result_url: Url = url


@dataclass
class BuildChrootParams(ParamsSchema):
    build_id: Integer = id_field
    chrootname: String = mock_chroot

    __all_required: bool = True


@dataclass
class BuildChrootConfig(Schema):
    additional_repos: List = fields.additional_repos
    additional_packages: List = fields.additional_packages
    with_opts: List = fields.with_opts
    without_opts: List = fields.without_opts
    enable_net: Boolean = fields.enable_net
    is_background: Boolean = fields.is_background
    memory_limit: Integer = fields.memory_limit
    timeout: Integer = fields.timeout
    bootstrap: String = fields.bootstrap
    bootstrap_image: String = fields.bootstrap_image
    repos: List = List(Nested(_repo_model))


@dataclass
class Nevra(Schema):
    arch: String = fields.arch
    epoch: Integer = fields.epoch
    release: String = fields.release
    version: String = fields.version
    name: String = String(description="Package name")


_nevra_model = Nevra.get_cls().model()


@dataclass
class NevraPackages(Schema):
    packages: List = List(Nested(_nevra_model))


@dataclass
class ModuleBuild(Schema):
    nsv: String = fields.nsv


@dataclass
class WebhookSecret(Schema):
    id_field: String = fields.id_field
    name: String = fields.name
    ownername: String = fields.ownername
    full_name: String = fields.full_name
    webhook_secret: String = fields.webhook_secret


@dataclass
class ModuleAdd(InputSchema):
    modulemd: String = fields.modulemd
    distgit: String = fields.distgit
    scmurl: String = fields.scmurl


@dataclass
class _ModulePackage(Schema):
    name: String = fields.name
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
    state: String = fields.state
    result_url: Url = fields.result_url


@dataclass
class SourceBuildConfig(Schema):
    source_type: String = fields.source_type
    source_dict: Raw = fields.source_dict
    memory_limit: Integer = fields.memory_limit
    timeout: Integer = fields.timeout
    is_background: Boolean = fields.is_background


@dataclass
class ListBuild(ParamsSchema):
    ownername: String = fields.ownername
    projectname: String = fields.projectname
    packagename: String = fields.packagename
    status: String = fields.status

    @property
    def required_attrs(self) -> list:
        return [self.ownername, self.projectname]


@dataclass
class _GenericBuildOptions:
    chroot_names: List = fields.chroot_names
    background: Boolean = fields.background
    timeout: Integer = fields.timeout
    bootstrap: String = fields.bootstrap
    isolation: String = fields.isolation
    after_build_id: Integer = fields.after_build_id
    with_build_id: Integer = fields.with_build_id
    packit_forge_project: String = fields.packit_forge_project
    enable_net: Boolean = fields.enable_net


@dataclass
class _BuildDataCommon:
    ownername: String = fields.ownername
    projectname: String = fields.projectname


@dataclass
class CreateBuildUrl(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    project_dirname: String = fields.project_dirname
    pkgs: List = List(
        Url,
        description="List of urls to build from",
        example=["https://example.com/some.src.rpm"],
    )


@dataclass
class CreateBuildUpload(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    project_dirname: String = fields.project_dirname
    pkgs: List = List(Raw, description="application/x-rpm files to build from")


@dataclass
class CreateBuildSCM(_BuildDataCommon, _GenericBuildOptions, _SourceDictScmFields, InputSchema):
    project_dirname: String = fields.project_dirname
    scm_type: String = fields.scm_type
    source_build_method: String = fields.source_build_method


@dataclass
class CreateBuildDistGit(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    distgit: String = fields.distgit
    namespace: String = fields.namespace
    package_name: String = fields.package_name
    committish: String = fields.committish
    project_dirname: String = fields.project_dirname


@dataclass
class CreateBuildPyPI(_BuildDataCommon, _GenericBuildOptions, SourceDictPyPI, InputSchema):
    project_dirname: String = fields.project_dirname


@dataclass
class CreateBuildRubyGems(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    project_dirname: String = fields.project_dirname
    gem_name: String = fields.gem_name


@dataclass
class CreateBuildCustom(_BuildDataCommon, _GenericBuildOptions, InputSchema):
    script: String = fields.script
    chroot: String = fields.chroot
    builddeps: String = fields.builddeps
    resultdir: String = fields.resultdir
    project_dirname: String = fields.project_dirname
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
