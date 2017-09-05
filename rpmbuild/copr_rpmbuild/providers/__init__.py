from ..helpers import SourceType
from .distgit import DistGitProvider
from .rubygems import RubyGemsProvider


__all__ = [DistGitProvider, RubyGemsProvider]


def factory(source_type):
    try:
        return {
            SourceType.DISTGIT: DistGitProvider,
            SourceType.RUBYGEMS: RubyGemsProvider,
        }[source_type]
    except KeyError:
        raise RuntimeError("No provider associated with this source type")
