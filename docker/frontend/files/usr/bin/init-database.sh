#!/bin/bash

cd /usr/share/copr/coprs_frontend/ && copr-frontend create-db --alembic alembic.ini
copr-frontend create-chroot \
    $(ls /etc/mock/{fedora,epel}-*-{i386,x86_64}.cfg |xargs -I{} -n1 basename {} .cfg)

# OIDC and Kerberos don't support auth on local developer instances without
# workarounds. Let's have a default user for easier onboarding.
copr-frontend add-user jdoe jdoe@example.com
copr-frontend alter-user jdoe --admin
