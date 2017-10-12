#!/bin/bash

export LANG=en_US.UTF-8

/usr/bin/supervisord -c /etc/supervisord.conf

supervisorctl start postgresql
su - postgres -c 'PGPASSWORD=coprpass ; createdb -E UTF8 coprdb ; yes $PGPASSWORD | createuser -P -sDR copr-fe'

/bin/bash
