# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure(2) do |config|
  config.vm.box = "bento/fedora-21"

  config.vm.provider "libvirt" do |v, override|
    override.vm.box = "humaton/fedora-21-cloud"
  end

  config.vm.network "forwarded_port", guest: 80, host: 5000

  config.vm.synced_folder ".", "/vagrant", type: "rsync"

  # Update the system
  config.vm.provision "shell",
    inline: "sudo yum -y install dnf"

  # Update the system
  config.vm.provision "shell",
    inline: "sudo dnf clean all && sudo dnf -y update"

  # Install packages to support Copr and building RPMs
  config.vm.provision "shell",
    inline: "sudo dnf -y install dnf-plugins-core tito "

  # Enable the Copr repository for dependencies
  config.vm.provision "shell",
    inline: "sudo dnf -y copr enable msuchy/copr"

  # Install build dependencies for Copr Frontend
  config.vm.provision "shell",
    inline: "sudo dnf -y builddep /vagrant/frontend/copr-frontend.spec"

  # Remove previous build, if any
  config.vm.provision "shell", 
    inline: "sudo rm -rf /tmp/tito",
    run: "always"

  # WORKAROUND: install redis which is needed for %check in spec
  config.vm.provision "shell",
    inline: "sudo dnf -y install redis"

  # WORKAROUND: start redis
  config.vm.provision "shell",
    inline: "sudo systemctl start redis",
    run: "always"

  # Build Copr Frontend
  config.vm.provision "shell",
    inline: "cd /vagrant/frontend/ && tito build --test --rpm",
    run: "always"

  # Install the Copr Frontend build
  config.vm.provision "shell",
    inline: "sudo dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm",
    run: "always"

  # ..
  config.vm.provision "shell",
    inline: "sudo dnf -y install copr-selinux postgresql-server"

  # ..
  config.vm.provision "shell",
    inline: "sudo postgresql-setup initdb"

  # ..
  config.vm.provision "shell",
    inline: "sudo systemctl start postgresql",
    run: "always"

  # ..
  config.vm.provision "shell",
    inline: "sudo su - postgres -c 'PGPASSWORD=coprpass ; createdb -E UTF8 coprdb ; yes $PGPASSWORD | createuser -P -sDR copr-fe'"

  # I want to prepend some lines to a file - I'll do it in three steps
  # 1.  backup the database config file
  config.vm.provision "shell",
    inline: "sudo mv /var/lib/pgsql/data/pg_hba.conf /tmp/pg_hba.conf"

  # 2.  write the lines
  config.vm.provision "shell",
    inline: "printf 'local coprdb copr-fe md5\nhost  coprdb copr-fe 127.0.0.1/8 md5\nhost  coprdb copr-fe ::1/128 md5\nlocal coprdb postgres  ident\n' | sudo tee /var/lib/pgsql/data/pg_hba.conf"

  # 3.  write the file back after those lines
  config.vm.provision "shell",
    inline: "sudo cat /tmp/pg_hba.conf | sudo tee -a  /var/lib/pgsql/data/pg_hba.conf"

  # ..
  config.vm.provision "shell",
    inline: "sudo systemctl reload postgresql"

  # ..
  config.vm.provision "shell",
    inline: "cd /usr/share/copr/coprs_frontend/ && sudo ./manage.py create_db --alembic alembic.ini"

  # ..
  config.vm.provision "shell",
    inline: ""

  # ..
  config.vm.provision "shell",
    inline: <<-FOO
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
  config.vm.provision "shell",
    inline: "sudo chown -R copr-fe:copr-fe /usr/share/copr"

  # ..
  config.vm.provision "shell",
    inline: "sudo chown -R copr-fe:copr-fe /var/log/copr"

  # ..
  config.vm.provision "shell",
    inline: "sudo systemctl restart httpd",
    run: "always"

end

