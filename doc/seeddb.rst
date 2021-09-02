.. _seeddb:

Populate DB with pruduction data
================================

While setting your local development environment, you might want to
populate your database with production data. This document describes
how to import a databse dump when using the docker-compose stack
provided together with Copr source code (see :ref:`contribute`).

First, obtain some SQL dump from the production instance. They are
generated daily.

https://copr.fedorainfracloud.org/db_dumps/

Stop your frontend container because it holds a session to your database::

    $ docker-compose stop frontend

Copy the db dump into the database container::

    $ docker cp copr_db-2021-09-02_03-16.gz copr_database_1:/tmp/

Then log into the machine::

    $ docker exec -it copr_database_1 /bin/bash

Import the database dump::

    bash-4.2$ dropdb coprdb
    bash-4.2$ createdb coprdb
    bash-4.2$ cat /tmp/copr_db-2021-09-02_03-16.gz | gunzip | psql coprdb

Cancel all unfinished builds to avoid overloading your machine with
unnecessary builds::

    bash-4.2$ psql coprdb
    coprdb=# UPDATE build SET source_status=2 WHERE source_status IN (3, 4, 6, 7, 9);
    coprdb=# UPDATE build_chroot SET status=2 WHERE status IN (3, 4, 6, 7, 9);

When running frontend from ``main`` updating the database schema may
be necessary::

    $ docker exec -it copr_frontend_1 /bin/bash
    [copr-fe@frontend /]$ cd /opt/copr/frontend/coprs_frontend/
    [copr-fe@frontend coprs_frontend]$ alembic-3 upgrade head
    [copr-fe@frontend coprs_frontend]$ exit

Finally, start the frontend container again::

    $ docker-compose start frontend
