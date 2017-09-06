from ..helpers import SourceType
from .distgit import DistGitProvider
from .rubygems import RubyGemsProvider
from .pypi import PyPIProvider
from .spec import SpecUrlProvider
from .scm import ScmProvider


__all__ = [DistGitProvider, RubyGemsProvider, PyPIProvider,
           SpecUrlProvider, ScmProvider]


def factory(source_type):
    try:
        return {
            SourceType.LINK: SpecUrlProvider,
            SourceType.DISTGIT: DistGitProvider,
            SourceType.RUBYGEMS: RubyGemsProvider,
            SourceType.PYPI: PyPIProvider,
            SourceType.GIT_AND_TITO: ScmProvider,
            SourceType.MOCK_SCM: ScmProvider,
        }[source_type]
    except KeyError:
        raise RuntimeError("No provider associated with this source type")
