#!/bin/bash

export SCRIPTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export LANG=en_US.utf8

dnf -y install git dnf-plugins-core

if [[ `pwd` =~ ^/mnt/tests.*$ ]]; then
    echo "Setting up native beaker environment."
    git clone https://pagure.io/copr/copr.git
    export COPRROOTDIR=$SCRIPTPATH/copr
else
    echo "Setting up from source tree."
    export COPRROOTDIR=$SCRIPTPATH/../../../
fi

# install files from 'files'
cp -rT $SCRIPTPATH/files /

dnf -y copr enable @copr/copr-dev
dnf -y install vagrant vagrant-libvirt jq rpkg

# enable libvirtd for Vagrant (distgit)
systemctl enable libvirtd && systemctl start libvirtd

# setup dist-git & copr-dist-git
tar -C $SCRIPTPATH/frontend-files -cf $COPRROOTDIR/frontend-files.tar .
cd $COPRROOTDIR
vagrant up frontend
vagrant ssh -c '
sudo tar -xf /vagrant/frontend-files.tar -C /
echo "*:*:coprdb:copr-fe:coprpass" > ~/.pgpass
chmod 600 ~/.pgpass
psql -U copr-fe coprdb < /setup-user.sql
sudo copr-frontend create-chroot fedora-24-x86_64
' frontend
rm $COPRROOTDIR/frontend-files.tar
