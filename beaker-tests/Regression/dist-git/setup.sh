#!/bin/bash

export SCRIPTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

if [[ `pwd` =~ ^/mnt/tests.*$ ]]; then
    echo "Setting up native beaker environment."
    git clone https://pagure.io/copr/copr.git
    export COPRROOTDIR=$SCRIPTPATH/copr
else
    echo "Setting up from source tree."
    export COPRROOTDIR=$SCRIPTPATH/../../../
fi

dnf -y copr enable @copr/copr
if [[ ! $RELEASETEST ]]; then
	dnf -y copr enable @copr/copr-dev
fi

dnf -y copr enable clime/dist-git

./create_loopback_devices_for_docker.sh # hack for running tests inside docker

dnf -y update
dnf -y install fedpkg-copr
dnf -y install git
dnf -y install tito
dnf -y install pyp2rpm
dnf -y install pyrpkg
dnf -y install jq
dnf -y install copr-mocks
dnf -y install cgit
dnf -y install dist-git
dnf -y install dist-git-selinux

export LANG=en_US.UTF-8

# install copr-mocks from sources
cd $COPRROOTDIR/mocks
dnf -y builddep copr-mocks.spec
if [[ ! $RELEASETEST ]]; then
	tito build -i --test --rpm
else
	tito build -i --offline --rpm
fi
cd -

# install copr-dist-git from sources
cd $COPRROOTDIR/dist-git
dnf -y builddep copr-dist-git.spec --allowerasing
if [[ ! $RELEASETEST ]]; then
	tito build -i --test --rpm
else
	tito build -i --offline --rpm
fi
cd -

# root user settings
rm -rf /root/.ssh/
ssh-keygen -f /root/.ssh/id_rsa -N '' -q < /dev/zero &> /dev/null

echo "\
Host *
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
" | tee /root/.ssh/config && chmod 600 /root/.ssh/config

# dist-git settings (copr-dist-git specific hack to make md5 uris work)
echo "\
AliasMatch \"/repo(/.*)/md5(/.*)\" \"/var/lib/dist-git/cache/lookaside\$1\$2\"
Alias /repo/ /var/lib/dist-git/cache/lookaside/
" | tee /etc/httpd/conf.d/dist-git/lookaside-copr.conf

# copr-dist-git settings
echo "\
[dist-git]
frontend_base_url=http://localhost:5000
frontend_auth=1234
" | tee /etc/copr/copr-dist-git.conf && chmod 644 /etc/copr/copr-dist-git.conf

echo "\
[user]
email = copr-devel@lists.fedorahosted.org
name = Copr dist git
" | tee /home/copr-dist-git/.gitconfig && chown copr-dist-git:copr-dist-git /home/copr-dist-git/.gitconfig

su - copr-dist-git -c "rm -rf ~/.ssh; ssh-keygen -f ~/.ssh/id_rsa -q -N ''"

echo "\
Host *
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
" | tee /home/copr-dist-git/.ssh/config && chown copr-dist-git:copr-dist-git /home/copr-dist-git/.ssh/config && chmod 600 /home/copr-dist-git/.ssh/config

# cgit settings
sed -e s/^cache-size.*// /etc/cgitrc | tee /etc/cgitrc
echo 'scan-path=/var/lib/dist-git/git' | tee -a /etc/cgitrc

# git settings
if ! id -u git &>/dev/null; then
    useradd git
fi

su - git -c "rm -rf ~/.ssh; mkdir ~/.ssh; touch ~/.ssh/authorized_keys"
chmod 700 /home/git/.ssh
chmod 600 /home/git/.ssh/authorized_keys
cat /root/.ssh/id_rsa.pub >> /home/git/.ssh/authorized_keys
cat /home/copr-dist-git/.ssh/id_rsa.pub >> /home/git/.ssh/authorized_keys

# copy test suite file
cp -rT files/ /

# setting correct permissions
chown -R git:git /home/git/

# install copr-mocks deps (why not covered by dnf -y builddep?)
if ! rpm -qa | grep copr-mocks; then
    dnf -y install python3-flask
    dnf -y install python3-flask-script
    dnf -y install python3-devel
fi

setenforce 0 # for mock-scm in docker, see https://bugzilla.redhat.com/show_bug.cgi?id=1416813

rm -f /run/nologin # fix for docker environment

# enable & start services
systemctl daemon-reload
systemctl enable httpd && systemctl start httpd
systemctl enable docker && systemctl start docker
systemctl enable copr-dist-git && systemctl start copr-dist-git
