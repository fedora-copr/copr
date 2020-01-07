#!/bin/bash

cd /usr/share/copr/coprs_frontend/ && sudo -u copr-fe copr-frontend create-db --alembic alembic.ini
sudo -u copr-fe copr-frontend create-chroot \
    $(ls /etc/mock/{fedora,epel}-*-{i386,x86_64}.cfg |xargs -I{} -n1 basename {} .cfg)

/usr/sbin/httpd -DFOREGROUND
