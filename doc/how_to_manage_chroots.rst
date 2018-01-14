.. _how_to_manage_chroots:

How to manage chroots
======================

This article explains how to enable new chroots when a new Fedora is released and also how to disable them once the particular Fedora version is not supported.


Enable chroots
--------------

Some requirements need to be met before you can add the chroot for new Fedora. Copr uses `Mock <https://github.com/rpm-software-management/mock>`_ for building packages, so before adding a new chroot, you need to `check if there is already available mock config <https://github.com/rpm-software-management/mock/tree/devel/mock-core-configs/etc/mock>`_ for it. In such case, you also need check in which version of the :code:`mock-core-configs` package it was added and be sure that the version is installed on builders.

Then you can easily add a new chroot by

::

    copr-frontend create_chroot <name>

After the Fedora release, you probably want to do something like this

::

    copr-frontend create_chroot fedora-27-x86_64 fedora-27-i386 fedora-27-ppc64le


Disable chroots
---------------

When some Fedora version reaches the end of its release cycle and is marked as EOL, you can safely disable its chroots. Though we want to keep the chroots enabled for a short period of time (few weeks) even after EOL, so our users can comfortably deal with it.

It can be done with

::

    copr-frontend alter_chroot --action deactivate <name>

After running such command, no data are going to be removed. All repositories for the chroot are preserved. It is just disabled and users can't build new packages in it anymore.


After a Fedora version is marked as EOL, you probably want to do something like this

::

    copr-frontend alter_chroot --action deactivate fedora-25-x86_64 fedora-25-i386 fedora-25-ppc64le
