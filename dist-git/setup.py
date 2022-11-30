#!/usr/bin/python

"""\
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package provides the DistGit component."""

import os
from setuptools import setup, find_packages


__description__ = "Copr DistGit component."
__author__ = "Copr Team"
__author_email__ = "copr-team@redhat.com"
__url__ = "https://github.com/fedora-copr/copr"

setup(
    name='copr-dist-git',
    version="0.59",
    description=__description__,
    long_description=__doc__,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='GPLv2+',
    packages=find_packages(exclude=('tests*',)),
    scripts=[os.path.join("run", p) for p in os.listdir("run")],
    include_package_data=True,
    zip_safe=False,
)
