#!/usr/bin/python

from setuptools import setup

long_description = """Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a python client to the copr service."""

from copr.client import __description__, __version__

requires = [
    'requests',
    'six'
]


__name__ = 'copr'
__version__ = __version__
__description__ = __description__
__author__ = "Valentin Gologuzov"
__author_email__ = "vgologuz@redhat.com"
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
        "Development Status :: 1 - Alpha",
    ],
    install_requires=requires,
    packages=['copr', 'copr.client', 'copr.test'],
    include_package_data=True,
    zip_safe=False,
)
