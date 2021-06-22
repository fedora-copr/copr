from setuptools import setup

import shutil
import sys

requires = [
    'flask',
    'six',
    'sphinxcontrib-httpdomain',
]


__name__ = 'copr-keygen'
__description__ = description = "Copr's subsystem that generates keys for package signing."
__author__ = "Valentin Gologuzov"
__author_email__ = "vgologuz@redhat.com"
__url__ = "https://pagure.io/copr/copr"


setup(
    name=__name__,
    version="1.80",
    description=__description__,
    author=__author__,
    author_email=__author_email__,
    url=__url__,
    license='GPLv2+',
    classifiers=[
        "License :: OSI Approved ::"
        " GNU General Public License v2 or later (GPLv2+)",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.7",
        "Topic :: System :: Archiving :: Packaging",
        "Development Status :: 3 - Alpha",
    ],
    install_requires=requires,
    package_dir={'': 'src'},
    packages=['copr_keygen'],
    include_package_data=True,
    zip_safe=False,
)

#TODO: fix dirty cleanup
shutil.rmtree("src/copr_keygen.egg-info")
