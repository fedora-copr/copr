from copr_common.enums import BuildSourceEnum

from .rubygems import RubyGemsProvider
from .pypi import PyPIProvider
from .spec import UrlProvider
from .scm import ScmProvider
from .custom import CustomProvider
from .distgit import DistGitProvider


__all__ = [RubyGemsProvider, PyPIProvider,
           UrlProvider, ScmProvider]


def factory(source_type):
    try:
        return {
            BuildSourceEnum.link: UrlProvider,
            BuildSourceEnum.upload: UrlProvider,
            BuildSourceEnum.rubygems: RubyGemsProvider,
            BuildSourceEnum.pypi: PyPIProvider,
            BuildSourceEnum.scm: ScmProvider,
            BuildSourceEnum.custom: CustomProvider,
            BuildSourceEnum.distgit: DistGitProvider,
        }[source_type]
    except KeyError:
        raise RuntimeError("No provider associated with this source type")
