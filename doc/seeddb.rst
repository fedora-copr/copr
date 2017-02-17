.. _seeddb:

Populate DB with pruduction-like data
=====================================

This article assumes that you have access to copr-fe-dev machine.

While setting your local development environment you might want to populate your database with production-like data.

First, obtain some SQL dump from copr-fe-dev (i.e. coprdb-2015-06-02.dump). This assumes that you are a Copr developer.

Then stop your httpd service because copr-frontend holds session to your database::

    sudo service httpd stop

If you are using Vagrantfile provided together with Copr source code, you already have a database created and if the dump creates the whole DB, you need to drop it first. Then import the dump::

    [vagrant@localhost ~]$ sudo su - postgres

    -bash-4.3$ psql

    postgres=# drop database coprdb;

    postgres=# \q

    -bash-4.3$ psql < /vagrant/coprdb-2015-06-02.dump

    -bash-4.3$ exit

To keep your database schema up-to-date, use alembic::

    [vagrant@localhost ~]$ sudo su - copr-fe

    -bash-4.3$ alembic upgrade head

    -bash-4.3$ exit

Finally start the httpd service again::

    [vagrant@localhost ~]$ sudo service httpd start
