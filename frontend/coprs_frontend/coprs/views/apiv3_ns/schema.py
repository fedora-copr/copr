"""
Sometime in the future, we can maybe drop this whole file and generate schemas
from SQLAlchemy models:
https://github.com/python-restx/flask-restx/pull/493/files

Things used for the output:

- *_schema - describes our output schemas
- *_field  - a schema is a dict of named fields
- *_model  - basically a pair schema and its name


Things used for parsing the input:

- *_parser - for documenting query parameters in URL and
             parsing POST values in input JSON
- *_arg    - a parser is composed from arguments
- *_params - for documenting path parameters in URL because parser
             can't be properly used for them [1]

[1] https://github.com/noirbizarre/flask-restplus/issues/146#issuecomment-212968591
"""


from flask_restx.reqparse import Argument, RequestParser
from flask_restx.fields import String, List, Integer, Boolean, Nested, Url, Raw
from flask_restx.inputs import boolean
from coprs.views.apiv3_ns import api


id_field = Integer(
    description="Numeric ID",
    example=123,
)

mock_chroot_field = String(
    description="Mock chroot",
    example="fedora-rawhide-x86_64",
)

ownername_field = String(
    description="User or group name",
    example="@copr",
)

projectname_field = String(
    description="Name of the project",
    example="copr-dev",
)

project_dirname_field = String(
    description="",
    example="copr-dev:pr:123",
)

packagename_field = String(
    description="Name of the package",
    example="copr-cli",
)

comps_name_field = String(
    description="Name of the comps.xml file",
)

additional_repos_field = List(
    String,
    description="Additional repos to be used for builds in this chroot",
)

additional_packages_field = List(
    String,
    description="Additional packages to be always present in minimal buildroot",
)

additional_modules_field = List(
    String,
    description=("List of modules that will be enabled "
                 "or disabled in the given chroot"),
    example=["module1:stream", "!module2:stream"],
)

with_opts_field = List(
    String,
    description="Mock --with option",
)

without_opts_field = List(
    String,
    description="Mock --without option",
)

delete_after_days_field = Integer(
    description="The project will be automatically deleted after this many days",
    example=30,
)

isolation_field = String(
    description=("Mock isolation feature setup. Possible values "
                 "are 'default', 'simple', 'nspawn'."),
    example="nspawn",
)

repo_priority_field = Integer(
    description="The priority value of this repository. Defaults to 99",
    example=42,
)

enable_net_field = Boolean(
    description="Enable internet access during builds",
)

source_type_field = String(
    description=("See https://python-copr.readthedocs.io"
                 "/en/latest/client_v3/package_source_types.html"),
    example="scm",
)

scm_type_field = String(
    default="Possible values are 'git', 'svn'",
    example="git",
)

scm_prepare_script = String(
    description="Script code sourced(!) by shell before running make (only with `make srpm` type)",
    example="MY_ENV_FOO=hello",
)

source_build_method_field = String(
    description="https://docs.pagure.org/copr.copr/user_documentation.html#scm",
    example="tito",
)

pypi_package_name_field = String(
    description="Package name in the Python Package Index.",
    example="copr",
)

pypi_package_version_field = String(
    description="PyPI package version",
    example="1.128pre",
)

# TODO We are copy-pasting descriptions from web UI to this file. This field
# is an ideal candidate for figuring out how to share the descriptions
pypi_spec_generator_field = String(
    description=("Tool for generating specfile from a PyPI package. "
                 "The options are full-featured pyp2rpm with cross "
                 "distribution support, and pyp2spec that is being actively "
                 "developed and considered to be the future."),
    example="pyp2spec",
)

pypi_spec_template_field = String(
    description=("Name of the spec template. "
                 "This option is limited to pyp2rpm spec generator."),
    example="default",
)

pypi_versions_field = List(
    String,  # We currently return string but should this be number?
    description=("For what python versions to build. "
                 "This option is limited to pyp2rpm spec generator."),
    example=["3", "2"],
)

auto_rebuild_field = Boolean(
    description="Auto-rebuild the package? (i.e. every commit or new tag)",
)

clone_url_field = String(
    description="URL to your Git or SVN repository",
    example="https://github.com/fedora-copr/copr.git",
)

committish_field = String(
    description="Specific branch, tag, or commit that you want to build",
    example="main",
)

subdirectory_field = String(
    description="Subdirectory where source files and .spec are located",
    example="cli",
)

spec_field = String(
    description="Path to your .spec file under the specified subdirectory",
    example="copr-cli.spec",
)

chroots_field = List(
    String,
    description="List of chroot names",
    example=["fedora-37-x86_64", "fedora-rawhide-x86_64"],
)

submitted_on_field = Integer(
    description="Timestamp when the build was submitted",
    example=1677695304,
)

started_on_field = Integer(
    description="Timestamp when the build started",
    example=1677695545,
)

ended_on_field = Integer(
    description="Timestamp when the build ended",
    example=1677695963,
)

is_background_field = Boolean(
    description="The build is marked as a background job",
)

submitter_field = String(
    description="Username of the person who submitted this build",
    example="frostyx",
)

state_field = String(
    description="",
    example="succeeded",
)

repo_url_field = Url(
    description="See REPO OPTIONS in `man 5 dnf.conf`",
    example="https://download.copr.fedorainfracloud.org/results/@copr/copr-dev/fedora-$releasever-$basearch/",
)

max_builds_field = Integer(
    description=("Keep only the specified number of the newest-by-id builds "
                 "(garbage collector is run daily)"),
    example=10,
)

source_package_url_field = String(
    description="URL for downloading the SRPM package"
)

source_package_version_field = String(
    description="Package version",
    example="1.105-1.git.53.319c6de",
)

gem_name_field = String(
    description="Gem name from RubyGems.org",
    example="hello",
)

custom_script_field = String(
    description="Script code to produce a SRPM package",
    example="#! /bin/sh -x",
)

custom_builddeps_field = String(
    description="URL to additional yum repos, which can be used during build.",
    example="copr://@copr/copr",
)

custom_resultdir_field = String(
    description="Directory where SCRIPT generates sources",
    example="./_build",
)

custom_chroot_field = String(
    description="What chroot to run the script in",
    example="fedora-latest-x86_64",
)

module_hotfixes_field = Boolean(
    description="Allow non-module packages to override module packages",
)

limit_field = Integer(
    description="Limit",
    example=20,
)

offset_field = Integer(
    description="Offset",
    example=0,
)

order_field = String(
    description="Order by",
    example="id",
)

order_type_field = String(
    description="Order type",
    example="DESC",
)

pagination_schema = {
    "limit_field": limit_field,
    "offset_field": offset_field,
    "order_field": order_field,
    "order_type_field": order_type_field,
}

pagination_model = api.model("Pagination", pagination_schema)

project_chroot_schema = {
    "mock_chroot": mock_chroot_field,
    "ownername": ownername_field,
    "projectname": projectname_field,
    "comps_name": comps_name_field,
    "additional_repos": additional_repos_field,
    "additional_packages": additional_packages_field,
    "additional_modules": additional_modules_field,
    "with_opts": with_opts_field,
    "without_opts": without_opts_field,
    "delete_after_days": delete_after_days_field,
    "isolation": isolation_field,
}

project_chroot_model = api.model("ProjectChroot", project_chroot_schema)

repo_schema = {
    "baseurl": String,
    "id": String(example="copr_base"),
    "name": String(example="Copr repository"),
    "module_hotfixes": module_hotfixes_field,
    "priority": repo_priority_field,
}

repo_model = api.model("Repo", repo_schema)

project_chroot_build_config_schema = {
    "chroot": mock_chroot_field,
    "repos": List(Nested(repo_model)),
    "additional_repos": additional_repos_field,
    "additional_packages": additional_packages_field,
    "additional_modules": additional_modules_field,
    "enable_net": enable_net_field,
    "with_opts":  with_opts_field,
    "without_opts": without_opts_field,
    "isolation": isolation_field,
}

project_chroot_build_config_model = \
    api.model("ProjectChrootBuildConfig", project_chroot_build_config_schema)

source_dict_scm_schema = {
    "clone_url": clone_url_field,
    "committish": committish_field,
    "source_build_method": source_build_method_field,
    "spec": spec_field,
    "subdirectory": subdirectory_field,
    "type": scm_type_field,
}

source_dict_scm_model = api.model("SourceDictSCM", source_dict_scm_schema)

source_dict_pypi_schema = {
    "pypi_package_name": pypi_package_name_field,
    "pypi_package_version": pypi_package_version_field,
    "spec_generator": pypi_spec_generator_field,
    "spec_template": pypi_spec_template_field,
    "python_versions": pypi_versions_field,
}

source_dict_pypi_model = api.model("SourceDictPyPI", source_dict_pypi_schema)

source_package_schema = {
    "name": packagename_field,
    "url": source_package_url_field,
    "version": source_package_version_field,
}

source_package_model = api.model("SourcePackage", source_package_schema)

build_schema = {
    "chroots": chroots_field,
    "ended_on": ended_on_field,
    "id": id_field,
    "is_background": is_background_field,
    "ownername": ownername_field,
    "project_dirname": project_dirname_field,
    "projectname": projectname_field,
    "repo_url": repo_url_field,
    "source_package": Nested(source_package_model),
    "started_on": started_on_field,
    "state": state_field,
    "submitted_on": submitted_on_field,
    "submitter": submitter_field,
}

build_model = api.model("Build", build_schema)

package_builds_schema = {
    "latest": Nested(build_model, allow_null=True),
    "latest_succeeded": Nested(build_model, allow_null=True),
}

package_builds_model = api.model("PackageBuilds", package_builds_schema)

# TODO We use this schema for both GetPackage and PackageEdit. The `builds`
# field is returned for both but only in case of GetPackage it can contain
# results. How should we document this?
package_schema = {
    "id": id_field,
    "name": packagename_field,
    "projectname": projectname_field,
    "ownername": ownername_field,
    "source_type": source_type_field,
    # TODO Somehow a Polymorh should be used here for `source_dict_scm_model`,
    # `source_dict_pypi_model`, etc. I don't know how, so leaving an
    # undocumented value for the time being.
    "source_dict": Raw,
    "auto_rebuild": auto_rebuild_field,
    "builds": Nested(package_builds_model),
}

package_model = api.model("Package", package_schema)


def clone(field):
    """
    Return a copy of a field
    """
    kwargs = field.__dict__.copy()
    return field.__class__(**kwargs)


add_package_params = {
    "ownername": ownername_field.description,
    "projectname": projectname_field.description,
    "package_name": packagename_field.description,
    "source_type_text": source_type_field.description,
}

edit_package_params = {
    **add_package_params,
    "source_type_text": source_type_field.description,
}

get_build_params = {
    "build_id": id_field.description,
}

def to_arg_type(field):
    """
    Take a field on the input, find out its type and convert it to a type that
    can be used with `RequestParser`.
    """
    types = {
        Integer: int,
        String: str,
        Boolean: boolean,
        List: list,
    }
    for key, value in types.items():
        if isinstance(field, key):
            return value
    raise RuntimeError("Unknown field type: {0}"
                       .format(field.__class__.__name__))


def field2arg(name, field, **kwargs):
    """
    Take a field on the input and create an `Argument` for `RequestParser`
    based on it.
    """
    return Argument(
        name,
        type=to_arg_type(field),
        help=field.description,
        **kwargs,
    )


def merge_parsers(a, b):
    """
    Take two `RequestParser` instances and create a new one, combining all of
    their arguments.
    """
    parser = RequestParser()
    for arg in a.args + b.args:
        parser.add_argument(arg)
    return parser


def get_package_parser():
    # pylint: disable=missing-function-docstring
    parser = RequestParser()
    parser.add_argument(field2arg("ownername", ownername_field, required=True))
    parser.add_argument(field2arg("projectname", projectname_field, required=True))
    parser.add_argument(field2arg("packagename", packagename_field, required=True))

    parser.add_argument(
        "with_latest_build", type=boolean, required=False, default=False,
        help=(
            "The result will contain 'builds' dictionary with the latest "
            "submitted build of this particular package within the project"))

    parser.add_argument(
        "with_latest_succeeded_build", type=boolean, required=False, default=False,
        help=(
            "The result will contain 'builds' dictionary with the latest "
            "successful build of this particular package within the project."))

    return parser


def add_package_parser():
    # pylint: disable=missing-function-docstring
    args = [
        # SCM
        field2arg("clone_url", clone_url_field),
        field2arg("committish", committish_field),
        field2arg("subdirectory", subdirectory_field),
        field2arg("spec", spec_field),
        field2arg("scm_type", scm_type_field),
        field2arg('prepare_script', scm_prepare_script)

        # Rubygems
        field2arg("gem_name", gem_name_field),

        # PyPI
        field2arg("pypi_package_name", pypi_package_name_field),
        field2arg("pypi_package_version", pypi_package_version_field),
        field2arg("spec_generator", pypi_spec_generator_field),
        field2arg("spec_template", pypi_spec_template_field),
        field2arg("python_versions", pypi_versions_field),

        # Custom
        field2arg("script", custom_script_field),
        field2arg("builddeps", custom_builddeps_field),
        field2arg("resultdir", custom_resultdir_field),
        field2arg("chroot", custom_chroot_field),


        field2arg("packagename", packagename_field),
        field2arg("source_build_method", source_build_method_field),
        field2arg("max_builds", max_builds_field),
        field2arg("webhook_rebuild", auto_rebuild_field),
    ]
    parser = RequestParser()
    for arg in args:
        arg.location = "json"
        parser.add_argument(arg)
    return parser


def edit_package_parser():
    # pylint: disable=missing-function-docstring
    parser = add_package_parser().copy()
    for arg in parser.args:
        arg.required = False
    return parser


def project_chroot_parser():
    # pylint: disable=missing-function-docstring
    parser = RequestParser()
    args = [
        field2arg("ownername", ownername_field),
        field2arg("projectname", projectname_field),
        field2arg("chrootname", mock_chroot_field),
    ]
    for arg in args:
        arg.required = True
        parser.add_argument(arg)
    return parser
