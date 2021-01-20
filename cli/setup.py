#!/usr/bin/python3

import codecs
import os
import re

from setuptools import setup, find_packages

long_description = """Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a command line interface to use copr."""

requires = [
    'copr',
    'humanize',
    'simplejson',
    'jinja2'
]

__name__ = 'copr-cli'
__description__ = "CLI tool to run copr"
__author__ = "Pierre-Yves Chibon"
__author_email__ = "pingou@pingoured.fr"
__url__ = "https://pagure.io/copr/copr"


setup(
    name=__name__,
    version="1.92",
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
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'copr-cli = copr_cli.main:main'
        ]
    },
)
