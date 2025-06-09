#!/usr/bin/python

import re
import os
import codecs
from setuptools import setup

long_description = """COPR is lightweight build system. It allows you to create new project
in WebUI, and submit new builds and COPR will create yum repository from latest builds.

This package contains python code used by other Copr packages. Mostly
useful for developers only."""


__description__ = "Common python code used by Copr."
__author__ = "Dominik Turecek"
__author_email__ = "dturecek@redhat.com"
__url__ = "https://github.com/fedora-copr/copr"


requires = [
    "filelock",
    "setproctitle",
]


setup(
    name='copr-common',
    version="1.1",
    description=__description__,
    long_description=long_description,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='GPLv2+',
    install_requires=requires,
    packages=['copr_common'],
    include_package_data=True,
    zip_safe=False
    )
