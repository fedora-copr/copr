#!/usr/bin/python

import re
import os
import codecs

from setuptools import setup

long_description = """Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a python client to the copr service."""


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


requires = [
    'marshmallow',
    'requests',
    'requests-toolbelt',
    'six'
]


__version__ = find_version('python-copr.spec')
__description__ = "Python client for copr service."
__author__ = "Valentin Gologuzov"
__author_email__ = "vgologuz@redhat.com"
__url__ = "http://fedorahosted.org/copr/"


setup(
    name='copr',
    version=__version__,
    description=__description__,
    long_description=long_description,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='GPLv2+',
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Topic :: System :: Archiving :: Packaging",
        "Development Status :: 3 - Alpha",
    ],
    install_requires=requires,
    packages=['copr', 'copr.client', 'copr.client_v2', 'copr.test'],
    include_package_data=True,
    zip_safe=False,
)
