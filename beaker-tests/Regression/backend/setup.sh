#!/bin/bash

export SCRIPTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export LANG=en_US.utf8

# primarily install git for the setup below
dnf -y install git

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

# install stuff needed for the test
dnf -y install docker
dnf -y install vagrant
dnf -y install vagrant-libvirt
dnf -y install jq
dnf -y install tito
dnf -y install wget

# enable libvirtd for Vagrant (distgit)
systemctl enable libvirtd && systemctl start libvirtd
systemctl start virtlogd.socket # this is currently needed in f25 for vagrant to work with libvirtd

# enable docker (backend)
./create_loopback_devices_for_docker.sh # hack for running tests inside docker
systemctl enable docker && systemctl start docker

# setup dist-git & copr-dist-git
tar -C $SCRIPTPATH/distgit-files -cf $COPRROOTDIR/distgit-files.tar .
cd $COPRROOTDIR
vagrant up distgit
vagrant ssh -c '
sudo rm -r /var/lib/copr-dist-git
sudo tar -xf /vagrant/distgit-files.tar -C /

sudo chown copr-dist-git:copr-dist-git -R /var/lib/copr-dist-git
sudo find /var/lib/copr-dist-git -type d -print0 | xargs -0 -n100 sudo chmod 775
sudo find /var/lib/copr-dist-git -type f -print0 | xargs -0 -n100 sudo chmod 664

sudo chown copr-dist-git:copr-dist-git -R /var/lib/dist-git/cache/lookaside
sudo find /var/lib/dist-git/cache/lookaside -type d -print0 | xargs -0 -n100 sudo chmod 775
sudo find /var/lib/dist-git/cache/lookaside -type f -print0 | xargs -0 -n100 sudo chmod 664

sudo chown copr-dist-git:packager -R /var/lib/dist-git/git
sudo find /var/lib/dist-git/git -type d -print0 | xargs -0 -n100 sudo chmod 2775
sudo find /var/lib/dist-git/git -type f -print0 | xargs -0 -n100 sudo chmod 664

sudo restorecon -r /var/lib/copr-dist-git
sudo restorecon -r /var/lib/dist-git
' distgit
rm $COPRROOTDIR/distgit-files.tar

# setup backend
cd $COPRROOTDIR/backend/docker
make del &> /dev/null # cleaning the previous instance (if any)
make build && make run
cd $SCRIPTPATH
docker exec copr-backend /bin/rm -r /var/lib/copr/public_html
docker cp backend-files/. copr-backend:/
docker exec copr-backend /bin/chown -R copr:copr /var/lib/copr/public_html
docker exec copr-backend /bin/sh -c 'rm -r /var/lib/copr-keygen/gnupg/*'
docker exec copr-backend /bin/sh -c 'rm -r /var/lib/copr-keygen/phrases/*'

# install copr-mocks from sources
cd $COPRROOTDIR/mocks
dnf -y install python3-flask
dnf -y install python3-flask-script
dnf -y builddep copr-mocks.spec
if [[ ! $RELEASETEST ]]; then
	tito build -i --test --rpm
else
	tito build -i --offline --rpm
fi
cd $SCRIPTPATH
