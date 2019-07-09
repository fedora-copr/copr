#! /usr/bin/python3
#
# Copyright (C) 2019  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import os

from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, "README.md")) as fd:
    README = fd.read()

__name__ = 'copr-messaging'
__description__ = "A schema and tooling for Copr fedora-messaging"
__author__ = "Copr team"
__author_email__ = "copr-devel@lists.fedorahosted.org"
__url__ = "https://pagure.io/copr/copr"
__version__ = "0.0"

__requires__ = [
    'fedora-messaging',
    'copr-common',
]

setup(
    name=__name__,
    version=__version__,
    description=__description__,
    long_description=README,
    url=__url__,

    # Possible options are at https://pypi.python.org/pypi?%3Aaction=list_classifiers
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 3.7",
    ],
    license="GPLv2+",
    maintainer="Copr Team",
    maintainer_email=__author_email__,
    keywords="fedora",
    packages=find_packages(
        exclude=("copr_messaging.tests",
                 "copr_messaging.tests.*")),
    include_package_data=True,
    zip_safe=False,
    install_requires=["fedora_messaging"],
    test_suite="copr_messaging.tests",
    entry_points={
        "fedora.messages": [
            "copr.build.start=copr_messaging.schema:BuildChrootStartedV1",
            "copr.build.end=copr_messaging.schema:BuildChrootEndedV1",

            # TODO: drop those entry points;  these shouldn't be needed once
            # all message consumers moved to `copr_messaging` module.
            "copr.chroot.start=copr_messaging.schema:BuildChrootStartedV1DontUse",
            "copr.unused.build.start=copr_messaging.schema:BuildChrootStartedV1Stomp",
            "copr.unused.build.end=copr_messaging.schema:BuildChrootEndedV1Stomp",
            "copr.unused.chroot.start=copr_messaging.schema:BuildChrootStartedV1StompDontUse",
        ]
    },
)
