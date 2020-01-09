#!/bin/bash

# @FIXME The `database` container can be up while postgresql can be unreachable for few miliseconds
# and therefore the alembic migration fails. Waiting 1s workarounds the issue
sleep 1

cd /usr/share/copr/coprs_frontend/ && sudo -u copr-fe copr-frontend create-db --alembic alembic.ini
sudo -u copr-fe copr-frontend create-chroot \
    $(ls /etc/mock/{fedora,epel}-*-{i386,x86_64}.cfg |xargs -I{} -n1 basename {} .cfg)

/usr/sbin/httpd -DFOREGROUND
