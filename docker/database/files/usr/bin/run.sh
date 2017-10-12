#!/bin/bash

export LANG=en_US.UTF-8

/usr/bin/supervisord -c /etc/supervisord.conf

runuser -l postgres -c "initdb -E UTF8 -D /var/lib/pgsql/data"
supervisorctl start postgresql
su - postgres -c 'PGPASSWORD=coprpass ; createdb -E UTF8 coprdb ; yes $PGPASSWORD | createuser -P -sDR copr-fe'

echo "listen_addresses = '*'" >> /var/lib/pgsql/data/postgresql.conf

# I want to prepend some lines to a file - I'll do it in three steps
# 1.  backup the database config file
mv /var/lib/pgsql/data/pg_hba.conf /tmp/pg_hba.conf

# 2.  write the lines
printf 'local coprdb copr-fe md5\nhost  coprdb copr-fe 127.0.0.1/8 md5\nhost  coprdb copr-fe ::1/128 md5\nlocal coprdb postgres  ident\nhost  coprdb copr-fe 172.18.0.0/12 md5\n' | tee /var/lib/pgsql/data/pg_hba.conf

# 3.  write the file back after those lines
cat /tmp/pg_hba.conf | tee -a  /var/lib/pgsql/data/pg_hba.conf

supervisorctl restart postgresql

/bin/bash
