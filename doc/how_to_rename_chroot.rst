.. _how_to_rename_chroot:

How to rename a chroot
================================

In the openEuler copr instance, we unfortunately need to rename a chroot.

The operations need to be done can be described as:

* [backend]: symlinks all the old chroot dir in resultdir to the new one
* [frontend]: change the os_release/os_version in frontend table mock_chroot
* [builder]: add new mock chroot configs to all builder

.. note::

    After these operations are complete, a new chroot will be displayed at all frontend pages, and all the old repo config files should be still usable.

To be more precisely, here are some operation details:

*Suppose you have a chroot named* ``foo-bar-x86_64`` *and want to rename it to* ``new-foo_bar-x86_64``

For backend
--------------
Login as copr user to backend node, and run:

.. code-block:: console

    $ /usr/bin/copr-rename-chroot --real-run  --pair foo-bar-x86_64:new-foo_bar-x86_64

Explain: the ``/usr/bin/copr-rename-chroot`` script will rename the dir in ``destdir`` from ``foo-bar-x86_64`` to ``new-foo_bar-x86_64``

.. warning::

    You may note the ``--real-run`` arguement, without it the script will perform a dry-run and just print the operations out.

    Run the command without ``real-run`` until you make sure all the operations are expected!

For frontend
--------------
Login to the frontend database and run:

.. code-block:: sql

    coprdb# UPDATE mock_chroot SET os_version='foo_bar', os_release='new' WHERE os_version='foo' AND os_release='bar' AND arch='x86_64'

Explain: the SQL will rename the old chroot which name is ``foo-bar-x86_64`` to ``new-foo_bar-x86_64`` in database, this operation will make webUI&copr-cli see the new chroot.

For builder
--------------
Update your mock package to ensure the ``new-foo_bar-x86_64.cfg`` existed!
