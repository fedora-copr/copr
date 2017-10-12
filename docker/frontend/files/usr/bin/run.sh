#!/bin/bash

export LANG=en_US.UTF-8

/usr/bin/supervisord -c /etc/supervisord.conf

runuser -l postgres -c "initdb -E UTF8 -D /var/lib/pgsql/data"
supervisorctl start postgresql
su - postgres -c 'PGPASSWORD=coprpass ; createdb -E UTF8 coprdb ; yes $PGPASSWORD | createuser -P -sDR copr-fe'


# I want to prepend some lines to a file - I'll do it in three steps
# 1.  backup the database config file
mv /var/lib/pgsql/data/pg_hba.conf /tmp/pg_hba.conf

# 2.  write the lines
printf 'local coprdb copr-fe md5\nhost  coprdb copr-fe 127.0.0.1/8 md5\nhost  coprdb copr-fe ::1/128 md5\nlocal coprdb postgres  ident\n' | tee /var/lib/pgsql/data/pg_hba.conf

# 3.  write the file back after those lines
cat /tmp/pg_hba.conf | tee -a  /var/lib/pgsql/data/pg_hba.conf

supervisorctl restart postgresql


cd /usr/share/copr/coprs_frontend/ && ./manage.py create_db --alembic alembic.ini
/usr/share/copr/coprs_frontend/manage.py create_chroot fedora-{22,23,rawhide}-{i386,x86_64,ppc64le} epel-{6,7}-x86_64 epel-6-i386
#RUN echo 'PEERDNS=no' | tee -a /etc/sysconfig/network
echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

cat <<EOF >> /etc/httpd/conf.d/copr.conf
<VirtualHost 0.0.0.0>
    WSGIPassAuthorization On
    WSGIDaemonProcess 127.0.0.1 user=copr-fe group=copr-fe threads=5
    WSGIScriptAlias / /usr/share/copr/coprs_frontend/application
    WSGIProcessGroup 127.0.0.1
    <Directory /usr/share/copr>
        WSGIApplicationGroup %{GLOBAL}
        Require all granted
    </Directory>
</VirtualHost>
EOF

# selinux: make data dir writeable for httpd
# TODO: probly correct solution is to uncomment first four lines in
# coprs_frontend/config/copr.conf so that data are stored under /var/lib
# and not under /usr/share/copr. copr-selinux does not account for storing
# data under /usr/share/copr/. Discuss this with peers.
chcon -R -t httpd_sys_rw_content_t /usr/share/copr/data

chown -R copr-fe:copr-fe /var/log/copr-frontend
chown -R copr-fe:copr-fe /usr/share/copr


echo "#########################################################" && \
    echo "###   Your development instance of Copr Frontend      ###" && \
    echo "###   is now running at: http://localhost:5000        ###" && \
    echo "#########################################################"

# Workaround
setenforce 0

supervisorctl restart httpd

/bin/bash
