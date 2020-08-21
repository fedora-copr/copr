from ..helpers import SourceType
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
            SourceType.LINK: UrlProvider,
            SourceType.UPLOAD: UrlProvider,
            SourceType.RUBYGEMS: RubyGemsProvider,
            SourceType.PYPI: PyPIProvider,
            SourceType.SCM: ScmProvider,
            SourceType.CUSTOM: CustomProvider,
            SourceType.DISTGIT: DistGitProvider,
        }[source_type]
    except KeyError:
        raise RuntimeError("No provider associated with this source type")
