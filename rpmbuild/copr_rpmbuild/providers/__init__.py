from ..helpers import SourceType
from .distgit import DistGitProvider
from .rubygems import RubyGemsProvider
from .pypi import PyPIProvider


__all__ = [DistGitProvider, RubyGemsProvider, PyPIProvider]


def factory(source_type):
    try:
        return {
            SourceType.DISTGIT: DistGitProvider,
            SourceType.RUBYGEMS: RubyGemsProvider,
            SourceType.PYPI: PyPIProvider,
        }[source_type]
    except KeyError:
        raise RuntimeError("No provider associated with this source type")
