.. _database_backup:

Database backups
================

We periodically create two kinds of database dumps.

Private/backup dump
-------------------

This "complete" dump is done for potential disaster-recovery situations.  It
contains all the data (including private stuff like API tokens), and therefore
we **never publish it or download it onto our machines**.  The dump is created in
the ``/backups/`` directory on Copr Frontend, and it is periodically pulled by
a rdiff-backup Fedora Infrastructure bot `configured by Ansible
<https://pagure.io/fedora-infra/ansible/blob/main/f/playbooks/rdiff-backup.yml>`_.

To generate the backup manually (this can be useful e.g. before upgrading to a
new major version of PostgreSQL), run::

    [root@copr-fe ~][PROD]# su - postgres
    bash-5.0$ /usr/local/bin/backup-database coprdb

.. warning::

    Please be aware that the script does an initial ``sleep`` for some
    undeterministic amount of time (to not backup all the Fedora Infra databases
    at the same time).  You might want to kill the ``sleep`` process to speed it
    up a little.  Still, be prepared that the dump, mostly because of the XZ
    compression, takes more than 20 minutes!

.. warning::

    If you run this manually to have the :ref:`last-minute pre-upgrade dump
    <how_to_upgrade_persistent_instances>`, you need to **keep the machine
    running** till the upgrade is done — to keep the ``/backups`` directory
    existing!

Public dumps
------------

These dumps are `publicly available
<https://copr.fedorainfracloud.org/db_dumps/>`_ for anyone's experiments.
These are generated overnight via::

    /etc/cron.d/cron-backup-database-coprdb

Those dumps have all the private data filtered out (namely the contents of
``_private`` tables), but still usable as-is for debugging purposes (e.g.
spawning a testing Copr Frontend container with pre-generated database).
