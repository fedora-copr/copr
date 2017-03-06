#!/usr/bin/env python3

import rpm
from setuptools import setup

spec_file = rpm.ts().parseSpec('prunerepo.spec')

print(spec_file.sourceHeader.version)

setup(
    name=spec_file.sourceHeader.name.decode("utf-8"),
    version=spec_file.sourceHeader.version.decode("utf-8"),
    description=spec_file.sourceHeader.summary.decode("utf-8"),
    long_description=spec_file.sourceHeader.description.decode("utf-8"),
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
