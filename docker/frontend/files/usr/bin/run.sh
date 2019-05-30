#!/bin/bash

export LANG=en_US.UTF-8

/usr/bin/supervisord -c /etc/supervisord.conf

cd /usr/share/copr/coprs_frontend/ && sudo -u copr-fe copr-frontend create_db --alembic alembic.ini
sudo -u copr-fe copr-frontend create_chroot fedora-{26,27,rawhide}-{i386,x86_64} epel-{6,7}-x86_64 epel-6-i386


# selinux: make data dir writeable for httpd
# TODO: probly correct solution is to uncomment first four lines in
# coprs_frontend/config/copr.conf so that data are stored under /var/lib
# and not under /usr/share/copr. copr-selinux does not account for storing
# data under /usr/share/copr/. Discuss this with peers.
chcon -R -t httpd_sys_rw_content_t /usr/share/copr/data

chown -R copr-fe:copr-fe /var/log/copr-frontend
chown -R copr-fe:copr-fe /usr/share/copr


echo "#########################################################"
echo "###   Your development instance of Copr Frontend      ###"
echo "###   is now running at: http://localhost:5000        ###"
echo "#########################################################"

# Workaround
setenforce 0

supervisorctl restart httpd

/bin/bash
