#!/bin/bash

export LANG=en_US.UTF-8

/usr/bin/supervisord -c /etc/supervisord.conf

chown -R copr-fe:copr-fe /var/log/copr-frontend
chown -R copr-fe:copr-fe /usr/share/copr

cd /usr/share/copr/coprs_frontend/ && sudo -u copr-fe copr-frontend create-db --alembic alembic.ini
sudo -u copr-fe copr-frontend create-chroot \
    $(ls /etc/mock/{fedora,epel}-*-{i386,x86_64}.cfg |xargs -I{} -n1 basename {} .cfg)

# selinux: make data dir writeable for httpd
# TODO: probly correct solution is to uncomment first four lines in
# coprs_frontend/config/copr.conf so that data are stored under /var/lib
# and not under /usr/share/copr. copr-selinux does not account for storing
# data under /usr/share/copr/. Discuss this with peers.
chcon -R -t httpd_sys_rw_content_t /usr/share/copr/data



echo "#########################################################"
echo "###   Your development instance of Copr Frontend      ###"
echo "###   is now running at: http://localhost:5000        ###"
echo "#########################################################"

# Workaround
setenforce 0

supervisorctl restart httpd

/bin/bash
