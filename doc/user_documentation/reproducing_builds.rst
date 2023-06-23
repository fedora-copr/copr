:orphan:

.. _reproducing_builds:

Reproducing Copr builds locally
===============================

In a nutshell, the build-logic in Copr is implemented as set of utilities that
form a thin wrapper around `Mock`_.  So `Mock needs to be configured`_.

Then, it should be relatively trivial to reproduce the build on your local
machine.  The howto is dumped into every single ``builder-live.log.gz`` file
like::

    You can reproduce this build on your computer by running:

      sudo dnf install copr-rpmbuild
      /usr/bin/copr-rpmbuild --verbose --drop-resultdir --task-url https://copr.fedorainfracloud.org/backend/get-build-task/6097492-fedora-rawhide-x86_64 --chroot fedora-rawhide-x86_64

Feel free to start with that workflow.  The Copr instance administrators should
pay attention to make the reproducibility as simple as that.  But some
situations may require additional configurations though; notable examples:

    1. You might need your own Red Hat ``subscription-manager`` credentials, if
       building against ``RHEL`` based chroots.

    2. Some configuration fixes in ``mock-core-configs`` package might be
       required (or additional configuration files added);  Copr administrators
       might do temporary hacks around broken distribution repositories, broken
       build methods, etc.  That's why the ``copr-rpmbuild`` utility dumps the
       ``configs.tar.gz`` file into every single result directory.  If needed,
       you can download the tarball and extract the appropriate piece of
       configuration into one of the `Mock configuration directories`_.

    3. For non-public DistGit instances, configured typically in non-public Copr
       instances, may need a config file in ``/etc/copr-distgit-client/``.  Ask
       your Copr admins to provide the configuration file for you.

    4. Uploaded spec files and SRPMs are very quickly removed from Copr
       Frontend, right after the sources are imported into DistGit.  Such
       "source builds" (not really builds in this sense) that just download
       stuff from Copr Frontend will fail for you locally claiming that the
       source doesn't exist, error 404.  This typically isn't a problem;  you
       don't want to reproduce "source build", but the particular binary RPM
       build.

.. _`Mock`: https://github.com/rpm-software-management/mock
.. _`Mock needs to be configured`: https://rpm-software-management.github.io/mock/#setup
.. _`Mock configuration directories`: https://rpm-software-management.github.io/mock/configuration
