#!/usr/bin/python

import re
import os
import codecs
from setuptools import setup

long_description = """COPR is lightweight build system. It allows you to create new project
in WebUI, and submit new builds and COPR will create yum repository from latest builds.

This package contains python code used by other Copr packages. Mostly
useful for developers only."""


def read(*parts):
    return codecs.open(os.path.join(os.path.dirname(__file__), *parts),
                       encoding='utf8').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^Version: (.*)$",
                              version_file, re.M)
    if version_match:
        return version_match.group(1).strip()
    raise RuntimeError("Unable to find version string.")


__version__ = find_version("python-copr-common.spec")
__description__ = "Common python code used by Copr."
__author__ = "Dominik Turecek"
__author_email__ = "dturecek@redhat.com"
__url__ = "https://pagure.io/copr/copr"


setup(
    name='copr_common',
    version=__version__,
    description=__description__,
    long_description=long_description,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='GPLv2+',
    packages=['copr_common'],
    include_package_data=True,
    zip_safe=False
    )
