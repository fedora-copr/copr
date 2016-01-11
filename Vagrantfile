# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|

  ###  FRONTEND  ###################################################
  config.vm.define "frontend" do |frontend|
    frontend.vm.box = "fedora/23-cloud-base"

    frontend.vm.network "forwarded_port", guest: 80, host: 5000

    frontend.vm.synced_folder ".", "/vagrant", type: "rsync"

    frontend.vm.network "private_network", ip: "192.168.242.51"

    # Update the system
    frontend.vm.provision "shell",
      inline: "sudo dnf clean all && sudo dnf -y update"

    # Install packages to support Copr and building RPMs
    frontend.vm.provision "shell",
      inline: "sudo dnf -y install dnf-plugins-core tito wget"

    # Enable the Copr repository for dependencies
    frontend.vm.provision "shell",
      # inline: "sudo dnf -y copr enable msuchy/copr"
      # WORKAROUND: old DNF plugin uses outdated .repo URL
      inline: "sudo wget https://copr.fedoraproject.org/coprs/msuchy/copr/repo/fedora-21/msuchy-copr-fedora-21.repo -P /etc/yum.repos.d/"

    # Install build dependencies for Copr Frontend
    frontend.vm.provision "shell",
      inline: "sudo dnf -y builddep /vagrant/frontend/copr-frontend.spec"

    # Remove previous build, if any
    frontend.vm.provision "shell", 
      inline: "sudo rm -rf /tmp/tito",
      run: "always"

    # WORKAROUND: install redis which is needed for %check in spec
    frontend.vm.provision "shell",
      inline: "sudo dnf -y install redis"

    # WORKAROUND: start redis
    frontend.vm.provision "shell",
      inline: "sudo systemctl start redis",
      run: "always"

    # Build Copr Frontend
    frontend.vm.provision "shell",
      inline: "cd /vagrant/frontend/ && tito build --test --rpm",
      run: "always"

    # Install the Copr Frontend build
    frontend.vm.provision "shell",
      inline: "sudo dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm",
      run: "always"

    # Configure dist git url
    frontend.vm.provision "shell",
      inline: "sed -e 's/^DIST_GIT_URL.*/DIST_GIT_URL = \"http:\\/\\/192.168.242.52\\/cgit\\/\"/' /etc/copr/copr.conf | sudo tee /etc/copr/copr.conf"

    # Configure dist git url
    frontend.vm.provision "shell",
      inline: "sed -e \"s/^#BACKEND_PASSWORD.*/BACKEND_PASSWORD = \\'1234\\'/\" /etc/copr/copr.conf | sudo tee /etc/copr/copr.conf"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo dnf -y install copr-selinux postgresql-server"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo postgresql-setup initdb"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo systemctl start postgresql",
      run: "always"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo su - postgres -c 'PGPASSWORD=coprpass ; createdb -E UTF8 coprdb ; yes $PGPASSWORD | createuser -P -sDR copr-fe'"

    # I want to prepend some lines to a file - I'll do it in three steps
    # 1.  backup the database config file
    frontend.vm.provision "shell",
      inline: "sudo mv /var/lib/pgsql/data/pg_hba.conf /tmp/pg_hba.conf"

    # 2.  write the lines
    frontend.vm.provision "shell",
      inline: "printf 'local coprdb copr-fe md5\nhost  coprdb copr-fe 127.0.0.1/8 md5\nhost  coprdb copr-fe ::1/128 md5\nlocal coprdb postgres  ident\n' | sudo tee /var/lib/pgsql/data/pg_hba.conf"

    # 3.  write the file back after those lines
    frontend.vm.provision "shell",
      inline: "sudo cat /tmp/pg_hba.conf | sudo tee -a  /var/lib/pgsql/data/pg_hba.conf"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo systemctl reload postgresql"

    # ..
    frontend.vm.provision "shell",
      inline: "cd /usr/share/copr/coprs_frontend/ && sudo ./manage.py create_db --alembic alembic.ini"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo /usr/share/copr/coprs_frontend/manage.py create_chroot fedora-{22,23,rawhide}-{i386,x86_64,ppc64le} epel-{6,7}-x86_64 epel-6-i386"

    # ..
    frontend.vm.provision "shell",
      inline: "echo 'PEERDNS=no' | sudo tee -a /etc/sysconfig/network"

    # ..
    frontend.vm.provision "shell",
      inline: "echo 'nameserver 8.8.8.8' | sudo tee -a /etc/resolv.conf"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo systemctl restart network"

    # ..
    frontend.vm.provision "shell", inline: <<-FOO
  echo \"
  <VirtualHost 0.0.0.0>

      WSGIPassAuthorization On
      WSGIDaemonProcess 127.0.0.1 user=copr-fe group=copr-fe threads=5
      WSGIScriptAlias / /usr/share/copr/coprs_frontend/application
      WSGIProcessGroup 127.0.0.1
      <Directory /usr/share/copr>
          WSGIApplicationGroup %{GLOBAL}
          Require all granted
      </Directory>
  </VirtualHost>
  \" | sudo tee /etc/httpd/conf.d/copr.conf 
  FOO

    # ..
    frontend.vm.provision "shell",
      inline: "sudo chown -R copr-fe:copr-fe /usr/share/copr"

    # selinux: make data dir writeable for httpd
    frontend.vm.provision "shell",
      inline: "chcon -R -t httpd_sys_rw_content_t /usr/share/copr/data",
      run: "always"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo chown -R copr-fe:copr-fe /var/log/copr"

    # ..
    frontend.vm.provision "shell",
      inline: "sudo systemctl restart httpd",
      run: "always"

    frontend.vm.provision "shell", run: "always", inline: <<-EOF
      echo "#########################################################"
      echo "###   Your development instance of Copr Frontend      ###" 
      echo "###   is now running at: http://localhost:5000        ###"
      echo "#########################################################"
    EOF
  end
  ###  DIST-GIT  ###################################################
  config.vm.define "distgit" do |distgit|

    distgit.vm.box = "centos/7"

    distgit.vm.network "forwarded_port", guest: 80, host: 5001

    distgit.vm.synced_folder ".", "/vagrant", type: "rsync"

    distgit.vm.network "private_network", ip: "192.168.242.52"

    # ...
#    distgit.vm.provision "shell",
#      inline: "sudo yum -y update"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo yum -y install epel-release"

    # ..
    distgit.vm.provision "shell",
      inline: <<-FOO
  echo \"
[asamalik-dist-git]
name=Copr repo for dist-git owned by asamalik
baseurl=https://copr-be.cloud.fedoraproject.org/results/asamalik/dist-git/epel-7-x86_64/
skip_if_unavailable=True
gpgcheck=1
gpgkey=https://copr-be.cloud.fedoraproject.org/results/asamalik/dist-git/pubkey.gpg
enabled=1
enabled_metadata=1

[msuchy-copr]
name=Copr repo for copr owned by msuchy
baseurl=https://copr-be.cloud.fedoraproject.org/results/msuchy/copr/epel-7-x86_64/
skip_if_unavailable=True
gpgcheck=1
gpgkey=https://copr-be.cloud.fedoraproject.org/results/msuchy/copr/pubkey.gpg
enabled=1
enabled_metadata=1
  \" | sudo tee /etc/yum.repos.d/dist-git-epel-7.repo
  FOO

    # ...
    distgit.vm.provision "shell",
      inline: "sudo yum -y install tito cgit dist-git dist-git-selinux pyrpkg"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo yum-builddep -y /vagrant/dist-git/copr-dist-git.spec"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo rm -rf /tmp/tito/*",
      run: "always"

    # ...
    distgit.vm.provision "shell",
      inline: "cd /vagrant/dist-git/ && tito build --test --rpm",
      run: "always"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo yum -y install /tmp/tito/noarch/copr-dist-git*.noarch.rpm || sudo yum -y upgrade /tmp/tito/noarch/copr-dist-git*.noarch.rpm || sudo yum -y downgrade /tmp/tito/noarch/copr-dist-git*.noarch.rpm",
      run: "always"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo chown root:packager /var/lib/dist-git/git && sudo chmod 775 /var/lib/dist-git/git"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo groupadd cvsadmin"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo useradd copr-dist-git -G cvsadmin,packager"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo useradd copr-service -G apache,packager,mock"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo su - copr-service -c \"ssh-keygen -f ~/.ssh/id_rsa -q -N ''\""

    # ...
    distgit.vm.provision "shell",
      inline: "sudo su - copr-dist-git -c \"mkdir ~/.ssh\""

    # ...
    distgit.vm.provision "shell",
      inline: "echo \"command=\\\"HOME=/var/lib/dist-git/git/ /usr/share/gitolite3/gitolite-shell copr-dist-git\\\" $(sudo cat /home/copr-service/.ssh/id_rsa.pub)\" | sudo su - copr-dist-git -c 'tee ~/.ssh/authorized_keys'"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo chmod 700 /home/copr-dist-git/.ssh"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo chmod 600 /home/copr-dist-git/.ssh/authorized_keys"

    # ...
    distgit.vm.provision "shell", inline: <<-EOF
echo \"[dist-git]
frontend_base_url=http://192.168.242.51
frontend_auth=1234
\" | sudo tee /etc/copr/copr-dist-git.conf && sudo chmod 644 /etc/copr/copr-dist-git.conf
    EOF

    # ...
    distgit.vm.provision "shell", inline: <<-EOF
echo \" [user]
        email = copr-devel@lists.fedorahosted.org
        name = Copr dist git\" | sudo tee /home/copr-service/.gitconfig && sudo chown copr-service:copr-service /home/copr-service/.gitconfig
    EOF

    # ...
    distgit.vm.provision "shell", inline: <<-EOF
echo \" 
alias /lookaside        /var/lib/dist-git/cache/lookaside
<Directory /var/lib/dist-git/cache/lookaside>
    Options Indexes FollowSymLinks
    AllowOverride None
    Require all granted
</Directory>
\" | sudo tee /etc/httpd/conf.d/dist-git/lookaside.conf
    EOF

    # ...
    distgit.vm.provision "shell", inline: <<-EOF
echo \" 
Alias /repo/ /var/lib/dist-git/cache/lookaside/
\" | sudo tee /etc/httpd/conf.d/dist-git/lookaside-copr.conf
    EOF

    # ...
    distgit.vm.provision "shell", inline: <<-EOF
echo \" 
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
\" | sudo tee /etc/dist-git/dist-git.conf && sudo chmod 644 /etc/dist-git/dist-git.conf
    EOF

    # ...
    distgit.vm.provision "shell", inline: <<-EOF
echo \"Host *
  StrictHostKeyChecking no
  UserKnownHostsFile /dev/null\" | sudo tee /home/copr-service/.ssh/config && sudo chown copr-service:copr-service /home/copr-service/.ssh/config && sudo chmod 600 /home/copr-service/.ssh/config
    EOF

    # ...
    distgit.vm.provision "shell",
      inline: "sudo chown copr-service:copr-service /var/log/copr-dist-git"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo chown copr-service:copr-service /var/lib/copr-dist-git"

    # ...
    distgit.vm.provision "shell",
      inline: "systemctl restart httpd && systemctl enable httpd"

    # ...
    distgit.vm.provision "shell",
      inline: "sed -e s/^cache-size.*// /etc/cgitrc | sudo tee /etc/cgitrc"

    # ...
    distgit.vm.provision "shell",
      inline: "echo 'project-list=/var/lib/copr-dist-git/cgit_pkg_list' | sudo tee -a /etc/cgitrc"

    # ...
    distgit.vm.provision "shell",
      inline: "echo 'scan-path=/var/lib/dist-git/git/rpms' | sudo tee -a /etc/cgitrc"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo /usr/share/dist-git/dist_git_sync.sh"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo systemctl start dist-git.socket && sudo systemctl enable dist-git.socket"

    # ...
    distgit.vm.provision "shell",
      inline: "sudo systemctl start copr-dist-git && sudo systemctl enable copr-dist-git"

    #...
    distgit.vm.provision "shell",
      inline: "sudo systemctl daemon-reload",
      run: "always"
    
    #...
    distgit.vm.provision "shell",
      inline: "sudo systemctl restart copr-dist-git",
      run: "always"

    distgit.vm.provision "shell", run: "always", inline: <<-EOF
      echo "#########################################################"
      echo "###   Your development instance of Copr Dist Git      ###" 
      echo "###   is now running at: http://localhost:5001/cgit   ###"
      echo "#########################################################"
    EOF
  end
end

