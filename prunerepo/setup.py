#!/usr/bin/python3

import os

from setuptools import setup

setup(
    name=os.getenv('name'),
    version=os.getenv('version'),
    description=os.getenv('summary'),
    author='clime',
    author_email='clime@redhat.com',
    download_url='https://pagure.io/copr/copr.git',
    license='GPLv2+',
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Build Tools",
    ],
    scripts=['prunerepo'],
    include_package_data=True,
)
