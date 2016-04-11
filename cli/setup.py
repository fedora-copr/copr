#!/usr/bin/python3

import codecs
import os
import re

from setuptools import setup

long_description = """Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a command line interface to use copr."""

requires = [
    'copr'
]


def read(*parts):
    return codecs.open(os.path.join(os.path.dirname(__file__), *parts),
                       encoding='utf8').read()


def find_version(*file_paths):
    version_file = read(*file_paths)
    version_match = re.search(r"^Version: (.*)$",
                              version_file, re.M)
    if version_match:
        return version_match.group(1)
    raise RuntimeError("Unable to find version string.")


__name__ = 'copr-cli'
__version__ = find_version('copr-cli.spec')
__description__ = "CLI tool to run copr"
__author__ = "Pierre-Yves Chibon"
__author_email__ = "pingou@pingoured.fr"
__url__ = "http://fedorahosted.org/copr/"


setup(
    name=__name__,
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
    packages=['copr_cli'],
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'copr-cli = copr_cli.main:main'
        ]
    },
)
