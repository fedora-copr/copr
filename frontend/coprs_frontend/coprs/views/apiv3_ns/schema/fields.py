"""
Fields for Flask-restx used in schemas.

Try to be consistent with field names and its corresponding names in API so
 dynamic creation of models works.
"""


from flask_restx.fields import String, List, Integer, Boolean, Raw, StringMixin

# TODO: split these fields to some hierarchy e.g. using dataclasses or to some clusters

# TODO: Use some shared constants for description - a lot of it is basically copied
#  description from forms

# TODO: some fields needs examples

# TODO: this file is not perfect in documenting... missing enums, choices, etc.


class Url(StringMixin, Raw):
    """
    Feel free to drop this if you want to spend 4 hours why the fuck everything
     stopped working. TLDR; query_to_parameters and flask_restx.fields.Url.output
     aren't friends.

    Flask_restx is opinionated and tries to follow some conventions, we break one of
     them by query_to_parameters decorator. The problem begins when Url field is used
     in marshaling because flask_restx tries to be clever and it is building example
     URL for you to documentation page as output. And to be even more clever, if no
     URL from user was provided, it uses flask.request.endpoint route and tries to
     build endpoint with correct values. Remember we tinker with the values in
     query_to_parameters so it screws.
    """
    __schema_format__ = "uri"

    def __init__(self, example=None, **kwargs):
        self.example = example or "https://www.example.uwu/xyz"
        super().__init__(example=example, **kwargs)


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

isolation = String(
    description=(
        "Mock isolation feature setup. Possible values "
        "are 'default', 'simple', 'nspawn'."
    ),
    example="nspawn",
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


committish = String(
    description="Specific branch, tag, or commit that you want to build",
    example="main",
)

chroots = List(
    String,
    description="List of chroot names",
    example=["fedora-37-x86_64", "fedora-rawhide-x86_64"],
)

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

state = String(
    description="",
    example="succeeded",
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


build_enable_net = Boolean(
    description="Enable networking for the builds",
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

bootstrap = String(
    description=(
        "Mock bootstrap feature setup. "
        "Possible values are 'default', 'on', 'off', 'image'."
    )
)

timeout = Integer(
    default=18000,
    example=123123,
    description="Number of seconds we allow the builds to run.",
)

version = String(example="1.0")

status = String(
    example="succeeded",
    description="Status of the build",
)

chroot_names = List(
    String,
    description="List of chroot names",
    example=["fedora-37-x86_64", "fedora-rawhide-x86_64"],
)

background = is_background

copr_dirname = project_dirname

distgit = String(
    description="Dist-git URL we build against",
    example="fedora",
)

# TODO: these needs description

memory_limit = Integer()

result_url = Url()
