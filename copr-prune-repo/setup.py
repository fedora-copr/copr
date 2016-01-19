#!/usr/bin/env python3
from distutils.core import setup

setup(name='copr-prune-repo',
      version='1.5',
      description='Remove failed and obsolete succeeded package builds from a copr repository',
      author='clime',
      author_email='clime@redhat.com',
      licence='GPLv2+',
      requires=['python3'],
      scripts=['copr_prune_repo'],
      long_description='Removes failed and obsolete succeeded builds (with the associated packages) from a copr repository. '+
                         'The build directories should belong to `copr` user and contain `build.info`, `fail` or `success` files, otherwise nothing gets deleted. '+
                         'The repository needs to be recreated manually afterwards with createrepo.'
)
