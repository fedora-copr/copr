#!/usr/bin/python

import re
import os
import codecs

from setuptools import setup, find_packages

long_description = """Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a python client to the copr service."""

requires = [
    'marshmallow',
    'requests',
    'requests-toolbelt',
    'six',
    'munch',
]

__description__ = "Python client for copr service."
__author__ = "Valentin Gologuzov"
__author_email__ = "vgologuz@redhat.com"
__url__ = "https://pagure.io/copr/copr"


setup(
    name='copr',
    version="1.108",
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        "Topic :: System :: Archiving :: Packaging",
        "Development Status :: 3 - Alpha",
    ],
    install_requires=requires,
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
)
