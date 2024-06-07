#!/bin/bash

cd /usr/share/copr/coprs_frontend/
copr-frontend create-db --alembic alembic.ini
copr-frontend create-chroot epel-next-8-x86_64-rpmfusion_nonfree
copr-frontend create-chroot epel-next-9-x86_64-rpmfusion_nonfree
copr-frontend create-chroot epel+rpmfusion_nonfree-7-x86_64
copr-frontend create-chroot epel+rpmfusion_nonfree-8-x86_64
copr-frontend create-chroot epel+rpmfusion_nonfree-9-x86_64
copr-frontend create-chroot fedora+rpmfusion_nonfree-39-x86_64
copr-frontend create-chroot fedora+rpmfusion_nonfree-40-x86_64
copr-frontend create-chroot fedora+rpmfusion_nonfree-rawhide-x86_64
