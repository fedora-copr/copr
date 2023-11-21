"""
File which contains only constants. Nothing else.
"""
from collections import namedtuple
from enum import Enum
from typing import Any

BANNER_LOCATION = "/var/lib/copr/data/banner-include.html"

DEFAULT_COPR_REPO_PRIORITY = 99


CommonAttribute = namedtuple(
    "CommonAttribute", ["description", "default"], defaults=("", None)
)


# just shortcut
c = CommonAttribute  # pylint: disable=invalid-name


# Common descriptions for forms, fields, etc.
class CommonDescriptions(Enum):
    """
    Enumerator for common descriptions and their default value between forms,
     fields, etc.
    """
    ADDITIONAL_PACKAGES = c(
        "Additional packages to be always present in minimal buildroot"
    )
    MOCK_CHROOT = c("Mock chroot", "fedora-latest-x86_64")
    ADDITIONAL_REPOS = c("Additional repos to be used for builds in this chroot")
    ENABLE_NET = c("Enable internet access during builds")
    PYPI_PACKAGE_NAME = c("Package name in the Python Package Index")
    PYPI_PACKAGE_VERSION = c("PyPI package version")
    SPEC_GENERATOR = c(
        "Tool for generating specfile from a PyPI package. "
        "The options are full-featured pyp2rpm with cross "
        "distribution support, and pyp2spec that is being actively "
        "developed and considered to be the future."
    )
    AUTO_REBUILD = c("Auto-rebuild the package? (i.e. every commit or new tag)")

    @property
    def description(self) -> str:
        """
        Get description of Enum member
        """
        return self.value.description

    @property
    def default(self) -> Any:
        """
        Fet default value of Enum member
        """
        return self.value.default
