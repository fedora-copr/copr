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

dnf -y copr enable @copr/copr-dev
dnf -y install jq copr-mocks dist-git dist-git-selinux rpkg

# cleanup
rm -r /tmp/rpkg/

# install copr-mocks from sources
cd $COPRROOTDIR/mocks
rpkg spec --outdir /tmp/rpkg
dnf -y builddep /tmp/rpkg/copr-mocks.spec
rpkg local --outdir /tmp/rpkg
dnf install -y /tmp/rpkg/noarch/copr-mocks*noarch.rpm --best
cd -

# install copr-dist-git from sources
cd $COPRROOTDIR/dist-git
rpkg spec --outdir /tmp/rpkg
dnf -y builddep /tmp/rpkg/copr-dist-git.spec --allowerasing
rpkg local --outdir /tmp/rpkg
dnf install -y /tmp/rpkg/noarch/copr-dist-git*noarch.rpm --best
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

# git settings
if ! id -u git &>/dev/null; then
    useradd git
fi

su - git -c "rm -rf ~/.ssh; mkdir ~/.ssh; touch ~/.ssh/authorized_keys"
chmod 700 /home/git/.ssh
chmod 600 /home/git/.ssh/authorized_keys
cat /root/.ssh/id_rsa.pub >> /home/git/.ssh/authorized_keys
cat /home/copr-dist-git/.ssh/id_rsa.pub >> /home/git/.ssh/authorized_keys

# copy test suite files
cp -rT files/ /

# setting correct permissions
chown -R git:git /home/git/

# install copr-mocks deps (why not covered by dnf -y builddep?)
if ! rpm -qa | grep copr-mocks; then
    dnf -y install python3-flask
    dnf -y install python3-devel
fi

rm -f /run/nologin # fix for docker environment

# we don't ssl here
rm -f /etc/httpd/conf.d/ssl.conf

# enable & start services
systemctl daemon-reload
systemctl enable httpd && systemctl start httpd
systemctl enable copr-dist-git && systemctl start copr-dist-git
