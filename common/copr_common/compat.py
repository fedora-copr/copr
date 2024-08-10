"""
A compatibility layer between already deprecated things from Rawhide and not
yet available replacements in old EPELs
"""


def package_version(name):
    """
    Return version of a given Python package

    The `importlib.metadata` module was introduced in Python 3.8 while
    EPEL 8 has Python 3.6. At the same time, `pkg_resources` is deprecated
    since Python 3.12 (Fedora 40):
    """
    # pylint: disable=import-outside-toplevel
    try:
        from importlib.metadata import distribution, PackageNotFoundError
        try:
            return distribution(name).version
        except PackageNotFoundError:
            return "git"
    except ImportError:
        import pkg_resources
        try:
            return pkg_resources.require(name)[0].version
        except pkg_resources.DistributionNotFound:
            return "git"
