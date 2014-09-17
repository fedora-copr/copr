Installation instructions
=========================

   **NB:** will be changed after addition of *copr-keygen* and
   *obs-signd* to Fedora repos.

At first we need to provide obs-signd packakge, which right now is
provided only for f21::

    wget https://kojipkgs.fedoraproject.org//packages/obs-signd/2.2.1/4.fc21/x86\_64/obs-signd-2.2.1-4.fc21.x86\_64.rpm
    sudo yum localinstall obs-signd-2.2.1-4.fc21.x86\_64.rpm -y

Install keygen service itself::

    sudo yum install copr-keygen

Next we need to copy config for httpd::

    cp /usr/share/copr-keygen/httpd/copr-keygen.conf.example /etc/httpd/conf.d/

Copy config for signd and edit allowed hosts::

    cp -f /usr/share/copr-keygen/sign/sign.conf/example /etc/sign/conf

Enable services and run them::

    systemctl enable signd httpd haveged
    systemctl start signd httpd haveged
