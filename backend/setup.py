#!/usr/bin/python

from setuptools import setup, find_packages

long_description = """\
COPR is lightweight build system. It allows you to create new project in WebUI,
and submit new builds and COPR will create yum repository from latest builds.

This package contains backend."""

__description__ = "Python client for copr service."
__author__ = "Copr Team"
__author_email__ = "copr-team@redhat.com"
__url__ = "https://github.com/fedora-copr/copr"


setup(
    name='copr-backend',
    version="1.163",
    description=__description__,
    long_description=long_description,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='GPLv2+',
    packages=find_packages(exclude=('tests*',)),
    package_data={'': ['*.j2']},
    include_package_data=True,
    zip_safe=False,
)
