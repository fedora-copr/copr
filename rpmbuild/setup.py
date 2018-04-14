#!/usr/bin/python3

from setuptools import setup, find_packages
setup(
    name="copr-rpmbuild",
    version='0.18',
    description="Run COPR build tasks",
    long_description="Run COPR build tasks",
    author='clime',
    author_email='clime@redhat.com',
    download_url='https://pagure.io/rpkg-client.git',
    license='GPLv2+',
    classifiers=[
        "License :: OSI Approved :: GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 3",
        "Topic :: Software Development :: Build Tools",
    ],
    packages=find_packages(exclude=['tests']),
    include_package_data=True
)
