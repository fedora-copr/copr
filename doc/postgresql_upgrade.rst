.. _postgresql_upgrade:


PostgreSQL Upgrade
==================

When upgrading to a distribution that provides a new major version of PostgreSQL server,
there is a manual intervention required.

Make sure ``httpd`` is stopped::

    [root@copr-fe-dev ~][STG]# systemctl stop httpd

Upgrade the database::

    [root@copr-fe-dev ~][STG]# dnf install postgresql-upgrade
    [root@copr-fe-dev ~][STG]# postgresql-setup --upgrade
    [root@copr-fe-dev ~][STG]# systemctl start postgresql

And rebuild indexes::

    [root@copr-fe-dev ~][STG]# su postgres
    bash-5.0$ cd
    bash-5.0$ reindexdb --all

Start ``httpd`` again::

    [root@copr-fe-dev ~][STG]# systemctl start httpd
