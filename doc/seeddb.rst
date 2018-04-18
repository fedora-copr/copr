.. _seeddb:

Populate DB with pruduction-like data
=====================================

This article assumes that you have an access to copr-fe-dev machine.

While setting your local development environment, you might want to populate your database with production-like data.

First, obtain some SQL dump from copr-fe-dev (i.e. ``coprdb-2015-06-02.sql``). This assumes that you are a Copr developer.

Then, if you are using docker-compose stack provided together with Copr source code (see :ref:`contribute`),
you can import the db dump into the Postgresql database used by copr-frontend container.

First see what's the name of the copr-frontend container e.g. by looking at ``docker ps`` output.

Let's say it is ``copr_frontend_1``.

Copy the db dump into the copr-frontend container:

::

    $ docker cp coprdb-2015-06-02.sql copr_frontend_1:/tmp/

Then log into the machine:

::

    $ docker exec -it copr_frontend_1 /bin/bash

Stop your httpd service because it holds a session to your database:

::

    [root@frontend /]# systemctl stop httpd

And continue with the import:

::

    [root@frontend ~]# su - postgres

    -bash-4.4$ dropdb coprdb

    -bash-4.4$ psql < /tmp/coprdb-2015-06-02.sql

    -bash-4.4$ exit

To keep your database schema up-to-date, use alembic:

::

    [root@frontend ~]$ cd /usr/share/copr/coprs_frontend/

    [root@frontend ~]$ su - copr-fe

    -bash-4.4$ alembic upgrade head

    -bash-4.4$ exit

Finally start the httpd service again:

::

    [root@frontend ~]# systemctl start httpd
