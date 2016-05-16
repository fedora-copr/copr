#!/bin/bash

export SCRIPTPATH="$( builtin cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

dnf -y copr enable @copr/copr-dev

dnf -y update
dnf -y install fedpkg-copr
dnf -y install git
dnf -y install tito
dnf -y install pyp2rpm
dnf -y install pyrpkg
dnf -y install jq

ssh-keygen -f /root/.ssh/id_rsa -N '' -q < /dev/zero &> /dev/null

if [ ! -e /root/.ssh/config ]; then
    echo "\
Host *
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
    " | tee /root/.ssh/config && chmod 600 /root/.ssh/config
fi

if ! rpm -qa | grep '^dist-git'; then
    dnf -y install dist-git
    dnf -y install dist-git-selinux
    echo "\
alias /lookaside /var/lib/dist-git/cache/lookaside
<Directory /var/lib/dist-git/cache/lookaside>
    Options Indexes FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>
    " | tee /etc/httpd/conf.d/dist-git/lookaside.conf
    echo "\
Alias /repo/ /var/lib/dist-git/cache/lookaside/
    " | tee /etc/httpd/conf.d/dist-git/lookaside-copr.conf
    echo "\
[acls]
user_groups=cvsadmin
admin_groups=cvsadmin
active_branches=el5,el6,el7,epel7,f21,f22,f23,master
reserved_branches=f[0-9][0-9],epel[0-9],epel[0-9][0-9],el[0-9],olpc[0-9]
pkgdb_acls_url=
pkgdb_groups_url=

[notifications]
email_domain=example.com
pkg_owner_emails=$PACKAGE-owner@example.com,commits@lists.example.com

[git]
default_branch_author=Copr Dist Git <copr-devel@lists.fedoraproject.org>
    " | tee /etc/dist-git/dist-git.conf && chmod 644 /etc/dist-git/dist-git.conf
    chown root:packager /var/lib/dist-git/git && chmod 775 /var/lib/dist-git/git
    groupadd cvsadmin
fi

if ! rpm -qa | grep copr-dist-git; then
    dnf -y install copr-dist-git
    echo "\
[dist-git]
frontend_base_url=http://localhost:5000
frontend_auth=1234
    " | tee /etc/copr/copr-dist-git.conf && chmod 644 /etc/copr/copr-dist-git.conf
fi

if ! rpm -qa | grep cgit; then
    dnf -y install cgit
    sed -e s/^cache-size.*// /etc/cgitrc | tee /etc/cgitrc
    echo 'project-list=/var/lib/copr-dist-git/cgit_pkg_list' | tee -a /etc/cgitrc
    echo 'scan-path=/var/lib/dist-git/git/rpms' | tee -a /etc/cgitrc
fi

if ! id -u copr-service &>/dev/null; then
    useradd copr-service -G packager,apache,mock
    su - copr-service -c "ssh-keygen -f ~/.ssh/id_rsa -q -N ''"
    echo "\
Host *
StrictHostKeyChecking no
UserKnownHostsFile /dev/null
    " | tee /home/copr-service/.ssh/config && chown copr-service:copr-service /home/copr-service/.ssh/config && chmod 600 /home/copr-service/.ssh/config
    echo "\
[user]
email = copr-devel@lists.fedorahosted.org
name = Copr dist git
    " | tee /home/copr-service/.gitconfig && chown copr-service:copr-service /home/copr-service/.gitconfig
    chown copr-service:copr-service /var/log/copr-dist-git
    chown copr-service:copr-service /var/lib/copr-dist-git
fi

if ! id -u copr-dist-git &>/dev/null; then
    useradd copr-dist-git -G cvsadmin,packager
    su - copr-dist-git -c "mkdir ~/.ssh"
    echo "command=\"HOME=/var/lib/dist-git/git/ /usr/share/gitolite3/gitolite-shell copr-dist-git\" $(cat /home/copr-service/.ssh/id_rsa.pub)" | su - copr-dist-git -c "tee ~/.ssh/authorized_keys"
    chmod 700 /home/copr-dist-git/.ssh
    chmod 600 /home/copr-dist-git/.ssh/authorized_keys
fi

if ! id -u git &>/dev/null; then
    useradd git
    su - git -c "mkdir ~/.ssh; touch ~/.ssh/authorized_keys"
    chmod 700 /home/git/.ssh
    chmod 600 /home/git/.ssh/authorized_keys
    cat /root/.ssh/id_rsa.pub >> /home/git/.ssh/authorized_keys
    cat /home/copr-service/.ssh/id_rsa.pub >> /home/git/.ssh/authorized_keys
fi

/usr/share/dist-git/dist_git_sync.sh

cp -rT files/ /

# setting correct permissions
chown -R git:git /home/git/

# clone copr repository
git clone https://github.com/fedora-copr/copr.git copr

# install copr-mocks deps (why not covered by dnf -y builddep?)
if ! rpm -qa | grep copr-mocks; then
    dnf -y install python3-flask
    dnf -y install python3-flask-script
    dnf -y install python3-devel
fi

# install copr-mocks from sources
cd $SCRIPTPATH/copr/mocks
dnf -y builddep copr-mocks.spec
tito build -i --test --rpm
cd -

# install copr-dist-git from sources
cd $SCRIPTPATH/copr/dist-git
dnf -y builddep copr-dist-git.spec
tito build -i --test --rpm
cd -

sudo dnf -y downgrade fedpkg-1.20 # fedpkg-1.22-3 is unsupported (downgrade to 1.20)
sudo dnf -y downgrade pyp2rpm # pyp2rpm-3.0.1 does not build srpms due to a bug

# enable & start services
systemctl daemon-reload
systemctl enable httpd && systemctl start httpd
systemctl enable copr-dist-git && systemctl start copr-dist-git
systemctl enable dist-git.socket && systemctl start dist-git.socket
systemctl enable copr-dist-git && systemctl start copr-dist-git
