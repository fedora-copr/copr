# pylint: disable=missing-class-docstring, too-many-instance-attributes
# pylint: disable=unused-private-member

"""
File for schemas, models and data validation for our API
"""


# dataclasses are written that way we can easily switch to marshmallow/pydantic
# as flask-restx docs suggests if needed


# TODO: in case we will use marshmallow/pydantic, we should share these schemas
#  somewhere - CLI, Frontend and backend shares these data with each other


from dataclasses import dataclass, fields, asdict, MISSING
from functools import cached_property, wraps
from typing import Any

from flask_restx.fields import String, List, Integer, Boolean, Nested, Url, Raw

from coprs.views.apiv3_ns import api
from coprs.views.apiv3_ns.schema import fields as schema_fields
from coprs.views.apiv3_ns.schema.fields import scm_type, mock_chroot, additional_repos


@dataclass
class Schema:
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
                result_schema[attr.name] = getattr(schema_fields, attr.name)
            else:
                result_schema[attr.name] = attr.default

        return result_schema

    @staticmethod
    def _convert_schema_class_dict_to_schema(d: dict) -> dict:
        unicorn_fields = {
            "id_field": "id",
        }
        # pylint: disable-next=consider-using-dict-items
        for field_to_rename in unicorn_fields:
            if field_to_rename in d:
                d[unicorn_fields[field_to_rename]] = d[field_to_rename]
                d.pop(field_to_rename)

        keys_to_delete = []
        for key in d:
            if key.startswith("_"):
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
        kls = cls(**schema_dict)
        setattr(
            kls,
            "__schema_dict",
            cls._convert_schema_class_dict_to_schema(schema_dict),
        )
        return kls

    @cached_property
    def schema(self):
        """
        Get schema dictionary with properly named key values.
        """
        schema_dict = getattr(self, "__schema_dict", None)
        if schema_dict is None:
            schema_dict = self._convert_schema_class_dict_to_schema(
                asdict(self)
            )

        return schema_dict

    def model(self):
        """
        Get Flask-restx model for the schema class.
        """
        return api.model(self.__class__.__name__, self.schema)


class InputSchema(Schema):
    @property
    def required_attrs(self) -> list:
        """
        Specify required attributes in model in these methods if needed.
        """
        return []

    def input_model(self):
        """
        Returns an input model (input to @ns.expect()) with properly set required
         parameters.
        """
        change_this_args_as_required = self.required_attrs
        if getattr(self, "__all_required", False):
            change_this_args_as_required = fields(self)

        for field in change_this_args_as_required:
            if "__all_required" == field:
                continue

            field.required = True

        return api.model(self.__class__.__name__, self.schema)


@dataclass
class PaginationMeta(Schema):
    limit: Integer
    offset: Integer
    order: String
    order_type: String


_pagination_meta_model = PaginationMeta.get_cls().model()


def _check_if_items_are_defined(method):
    @wraps(method)
    def check_items(self, *args, **kwargs):
        if getattr(self, "items") is None:
            raise KeyError(
                "No items are defined in Pagination. Perhaps you forgot to"
                " specify it when creating Pagination instance?"
            )
        return method(self, *args, **kwargs)

    return check_items


@dataclass
class Pagination(Schema):
    items: Any = None
    meta: Nested = Nested(_pagination_meta_model)

    @_check_if_items_are_defined
    def model(self):
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
class ProjectChrootGet(InputSchema):
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
class PackageGet(InputSchema):
    ownername: String
    projectname: String
    packagename: String
    with_latest_build: Boolean
    with_latest_succeeded_build: Boolean

    @property
    def required_attrs(self) -> list:
        return [self.ownername, self.projectname, self.packagename]


@dataclass
class PackageAdd(_SourceDictScmFields, SourceDictPyPI, InputSchema):
    # rest of SCM
    scm_type: String

    # Rubygems
    gem_name: String

    # Custom
    script: String
    builddeps: String
    resultdir: String
    chroot: String

    packagename: String
    source_build_method: String
    max_builds: Integer
    webhook_rebuild: Boolean


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
class ProjectGet(InputSchema):
    ownername: String
    projectname: String

    __all_required: bool = True


# OUTPUT MODELS
project_chroot_model = ProjectChroot.get_cls().model()
project_chroot_build_config_model = ProjectChrootBuildConfig.get_cls().model()
source_dict_scm_model = SourceDictScm.get_cls().model()
source_dict_pypi_model = SourceDictPyPI.get_cls().model()
package_model = Package.get_cls().model()
project_model = Project.get_cls().model()

pagination_project_model = Pagination(items=List(Nested(project_model))).model()

source_package_model = _source_package_model
build_model = _build_model
package_builds_model = _package_builds_model
repo_model = _repo_model


# INPUT MODELS
package_get_input_model = PackageGet.get_cls().input_model()
package_add_input_model = PackageAdd.get_cls().input_model()
package_edit_input_model = package_add_input_model

project_chroot_get_input_model = ProjectChrootGet.get_cls().input_model()

project_get_input_model = ProjectGet.get_cls().input_model()
project_add_input_model = ProjectAdd.get_cls().input_model()
project_edit_input_model = ProjectEdit.get_cls().input_model()
project_fork_input_model = ProjectFork.get_cls().input_model()
project_delete_input_model = ProjectDelete.get_cls().input_model()
