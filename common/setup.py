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
__url__ = "https://pagure.io/copr/copr"


setup(
    name='copr-common',
    version="0.8",
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
