.. _database_backup:

Database backup
===============

We periodically create a databse dump and offer users to download
it. At the same time, it can be used as a database backup if something
wrong happens. Please see ``/etc/cron.d/cron-backup-database-coprdb``.

To backup the database manually (this can be useful e.g. before
upgrading to a new major version of PostgreSQL), run::

    [root@copr-fe ~][PROD]# su - postgres
    bash-5.0$ /usr/local/bin/backup-database coprdb

Please be aware that the script does ``sleep`` for some
undeterministic amount of time. You might want to kill the ``sleep``
process to speed it up a little.
