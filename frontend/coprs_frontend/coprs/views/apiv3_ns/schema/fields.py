"""
Fields for Flask-restx used in schemas.

Try to be consistent with field names and its corresponding names in API so
 dynamic creation of models works.
"""


from flask_restx.fields import String, List, Integer, Boolean, Url, Raw

# TODO: split these fields to some hierarchy e.g. using dataclasses or to some clusters

# TODO: Use some shared constants for description - a lot of it is basically copied
#  description from forms

# TODO: some fields needs examples

# TODO: this file is not perfect in documenting... missing enums, choices, etc.


id_field = Integer(
    description="Numeric ID",
    example=123,
)

mock_chroot = String(
    description="Mock chroot",
    example="fedora-rawhide-x86_64",
)

ownername = String(
    description="User or group name",
    example="@copr",
)

full_name = String(
    description="Full name of the project",
    example="@copr/pull-requests",
)

projectname = String(
    description="Name of the project",
    example="copr-dev",
)

project_dirname = String(
    description="",
    example="copr-dev:pr:123",
)

packagename = String(
    description="Name of the package",
    example="copr-cli",
)

package_name = packagename

comps_name = String(
    description="Name of the comps.xml file",
)

additional_repos = List(
    String,
    description="Additional repos to be used for builds in this chroot",
)

additional_packages = List(
    String,
    description="Additional packages to be always present in minimal buildroot",
)

additional_modules = List(
    String,
    description=(
        "List of modules that will be enabled " "or disabled in the given chroot"
    ),
    example=["module1:stream", "!module2:stream"],
)

with_opts = List(
    String,
    description="Mock --with option",
)

without_opts = List(
    String,
    description="Mock --without option",
)

delete_after_days = Integer(
    description="The project will be automatically deleted after this many days",
    example=30,
)

isolation = String(
    description=(
        "Mock isolation feature setup. Possible values "
        "are 'default', 'simple', 'nspawn'."
    ),
    example="nspawn",
)

repo_priority = Integer(
    description="The priority value of this repository. Defaults to 99",
    example=42,
)

enable_net = Boolean(
    description="Enable internet access during builds",
)

source_type = String(
    description=(
        "See https://python-copr.readthedocs.io"
        "/en/latest/client_v3/package_source_types.html"
    ),
    example="scm",
)

scm_type = String(
    default="Possible values are 'git', 'svn'",
    example="git",
)

source_build_method = String(
    description="https://docs.pagure.org/copr.copr/user_documentation.html#scm",
    example="tito",
)

pypi_package_name = String(
    description="Package name in the Python Package Index.",
    example="copr",
)

pypi_package_version = String(
    description="PyPI package version",
    example="1.128pre",
)

# TODO We are copy-pasting descriptions from web UI to this file. This field
# is an ideal candidate for figuring out how to share the descriptions
spec_generator = String(
    description=(
        "Tool for generating specfile from a PyPI package. "
        "The options are full-featured pyp2rpm with cross "
        "distribution support, and pyp2spec that is being actively "
        "developed and considered to be the future."
    ),
    example="pyp2spec",
)

spec_template = String(
    description=(
        "Name of the spec template. "
        "This option is limited to pyp2rpm spec generator."
    ),
    example="default",
)

python_versions = List(
    String,  # We currently return string but should this be number?
    description=(
        "For what python versions to build. "
        "This option is limited to pyp2rpm spec generator."
    ),
    example=["3", "2"],
)

auto_rebuild = Boolean(
    description="Auto-rebuild the package? (i.e. every commit or new tag)",
)

clone_url = String(
    description="URL to your Git or SVN repository",
    example="https://github.com/fedora-copr/copr.git",
)

committish = String(
    description="Specific branch, tag, or commit that you want to build",
    example="main",
)

subdirectory = String(
    description="Subdirectory where source files and .spec are located",
    example="cli",
)

spec = String(
    description="Path to your .spec file under the specified subdirectory",
    example="copr-cli.spec",
)

chroots = List(
    String,
    description="List of chroot names",
    example=["fedora-37-x86_64", "fedora-rawhide-x86_64"],
)

chroots.clone()

submitted_on = Integer(
    description="Timestamp when the build was submitted",
    example=1677695304,
)

started_on = Integer(
    description="Timestamp when the build started",
    example=1677695545,
)

ended_on = Integer(
    description="Timestamp when the build ended",
    example=1677695963,
)

is_background = Boolean(
    description="The build is marked as a background job",
)

submitter = String(
    description="Username of the person who submitted this build",
    example="frostyx",
)

state = String(
    description="",
    example="succeeded",
)

repo_url = Url(
    description="See REPO OPTIONS in `man 5 dnf.conf`",
    example="https://download.copr.fedorainfracloud.org/results/@copr/copr-dev/fedora-$releasever-$basearch/",
)

max_builds = Integer(
    description=(
        "Keep only the specified number of the newest-by-id builds "
        "(garbage collector is run daily)"
    ),
    example=10,
)

source_package_url = String(description="URL for downloading the SRPM package")

source_package_version = String(
    description="Package version",
    example="1.105-1.git.53.319c6de",
)

gem_name = String(
    description="Gem name from RubyGems.org",
    example="hello",
)

script = String(
    description="Script code to produce a SRPM package",
    example="#! /bin/sh -x",
)

builddeps = String(
    description="URL to additional yum repos, which can be used during build.",
    example="copr://@copr/copr",
)

resultdir = String(
    description="Directory where SCRIPT generates sources",
    example="./_build",
)

chroot = String(
    description="What chroot to run the script in",
    example="fedora-latest-x86_64",
)

module_hotfixes = Boolean(
    description="Allow non-module packages to override module packages",
)

limit = Integer(
    description="Limit",
    example=20,
)

offset = Integer(
    description="Offset",
    example=0,
)

order = String(
    description="Order by",
    example="id",
)

order_type = String(
    description="Order type",
    example="DESC",
)

homepage = Url(
    description="Homepage URL of Copr project",
    example="https://github.com/fedora-copr",
)

contact = String(
    description="Contact email",
    example="pretty_user@fancydomain.uwu",
)

description = String(
    description="Description of Copr project",
)

instructions = String(
    description="Instructions how to install and use Copr project",
)

persistent = Boolean(
    description="Build and project is immune against deletion",
)

unlisted_on_hp = Boolean(
    description="Don't list Copr project on home page",
)

auto_prune = Boolean(
    description="Automatically delete builds in this project",
)

build_enable_net = Boolean(
    description="Enable networking for the builds",
)

appstream = Boolean(
    description="Enable Appstream for this project",
)

packit_forge_projects_allowed = String(
    description=(
        "Whitespace separated list of forge projects that will be "
        "allowed to build in the project via Packit"
    ),
    example="github.com/fedora-copr/copr github.com/another/project",
)

follow_fedora_branching = Boolean(
    description=(
        "If chroots for the new branch should be auto-enabled and populated from "
        "rawhide ones"
    ),
)

with_latest_build = Boolean(
    description=(
        "The result will contain 'builds' dictionary with the latest "
        "submitted build of this particular package within the project"
    ),
    default=False,
)

with_latest_succeeded_build = Boolean(
    description=(
        "The result will contain 'builds' dictionary with the latest "
        "successful build of this particular package within the project."
    ),
    default=False,
)

fedora_review = Boolean(
    description="Run fedora-review tool for packages in this project"
)

runtime_dependencies = String(
    description=(
        "List of external repositories (== dependencies, specified as baseurls)"
        "that will be automatically enabled together with this project repository."
    )
)

bootstrap_image = String(
    description=(
        "Name of the container image to initialize"
        "the bootstrap chroot from.  This also implies bootstrap=image."
        "This is a noop parameter and its value is ignored."
    )
)

name = String(description="Name of the project", example="Copr repository")

source_dict = Raw(
    description="http://python-copr.readthedocs.io/en/latest/client_v3/package_source_types.html"
)

devel_mode = Boolean(description="If createrepo should run automatically")

bootstrap = String(
    description=(
        "Mock bootstrap feature setup. "
        "Possible values are 'default', 'on', 'off', 'image'."
    )
)

confirm = Boolean(
    description=(
        "If forking into a existing project, this needs to be set to True,"
        "to confirm that user is aware of that."
    )
)

exist_ok = Boolean(
    description=(
        "Don't fail if a project with this owner and name already exist, "
        "return the existing instance instead. Please be aware that the "
        "project attributes are not updated in such case."
    )
)

# TODO: these needs description

chroot_repos = Raw()

multilib = Boolean()

verify = Boolean()

priority = Integer()

# TODO: specify those only in Repo schema?

baseurl = Url()

url = String()

version = String()

webhook_rebuild = Boolean()


def clone(field):
    """
    Return a copy of a field
    """
    if hasattr(field, "clone") and callable(getattr(field, "clone")):
        return field.clone()

    kwargs = field.__dict__.copy()
    return field.__class__(**kwargs)
