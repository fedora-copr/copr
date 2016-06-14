FROM fedora:23
MAINTAINER clime@redhat.com

# base packages
RUN dnf -y update
RUN dnf -y install dnf-plugins-core
RUN dnf -y install htop
RUN dnf -y install tito
RUN dnf -y install wget
RUN dnf -y install net-tools
RUN dnf -y install iputils
RUN dnf -y install vim
RUN dnf -y install mlocate
RUN dnf -y install git
RUN dnf -y install sudo
RUN dnf -y install python-nova
RUN dnf -y install openssh-server
RUN dnf -y install supervisor
RUN dnf -y install psmisc

# enable copr dev repo for package overrides
RUN dnf -y copr enable @copr/copr-dev

# preinstall backend and its builddeps to utilize most of Docker cache
RUN dnf -y install copr-backend
RUN cd `mktemp -d` && dnf -y download --source copr-backend && dnf -y builddep *.src.rpm

# builder packages
RUN dnf -y install fedpkg-copr
RUN dnf -y install packagedb-cli
RUN dnf -y install fedora-cert
RUN dnf -y install mock
RUN dnf -y install mock-lvm
RUN dnf -y install createrepo
RUN dnf -y install yum-utils
RUN dnf -y install pyliblzma
RUN dnf -y install rsync
RUN dnf -y install openssh-clients
RUN dnf -y install libselinux-python
RUN dnf -y install libsemanage-python
RUN dnf -y install rpm
RUN dnf -y install glib2
RUN dnf -y install ca-certificates
RUN dnf -y install scl-utils-build
RUN dnf -y install ethtool
RUN dnf -y install copr-keygen
RUN dnf -y install nginx

RUN echo '127.0.0.1 keygen' > /etc/hosts

RUN export LANG=en_US.utf8
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

RUN echo 'root:passwd' | chpasswd
RUN mkdir /root/.ssh &&  chmod 700 /root /root/.ssh
RUN touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys
RUN ssh-keygen -f /root/.ssh/id_rsa -N '' -q -C root@locahost
RUN cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys

RUN echo 'copr:passwd' | chpasswd
RUN echo 'copr ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN mkdir -p /home/copr/.ssh && chmod 700 /home/copr /home/copr/.ssh
RUN ssh-keygen -f /home/copr/.ssh/id_rsa -N '' -q -C copr@locahost
RUN touch /home/copr/.ssh/authorized_keys && chmod 600 /home/copr/.ssh/authorized_keys
RUN cat /home/copr/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
RUN cat /home/copr/.ssh/id_rsa.pub >> /home/copr/.ssh/authorized_keys
RUN chown copr:copr -R /home/copr
RUN usermod -a -G mock copr

RUN dnf -y install uwsgi
RUN dnf -y install uwsgi-plugin-python
RUN mkdir /var/log/uwsgi
RUN chown apache:apache /var/log/uwsgi

# perhaps change umask instead of this
RUN chmod 775 /var/log/uwsgi

RUN chown apache:apache /var/run/uwsgi
RUN chmod 775 /var/run/uwsgi

RUN usermod copr-signer -G apache

COPY . /copr
RUN dnf -y builddep /copr/backend/copr-backend.spec --allowerasing # fix for python-requests package (the cmd is failing python2-requests is already installed)
RUN rm -rf /tmp/tito && cd /copr/backend && LANG=en_US.UTF-8 tito build --test --rpm
RUN dnf -y install /tmp/tito/noarch/copr-backend*.noarch.rpm

COPY backend/docker/files/ /
RUN chmod 700 /root && chmod 700 /home/copr && chown copr:copr /home/copr # fix permission after COPY

RUN chown copr-signer:apache /etc/uwsgi.d/copr-keygen.ini

RUN dnf -y downgrade fedpkg # temporary fix cause fedpkg-copr doesn't work with the new version of fedpkg
RUN dnf -y install ansible1.9 --allowerasing # copr does not support ansible2 yet

# todo: it seems config in /etc/sysctl.conf is not taken into account
#RUN echo 4096 > /proc/sys/net/core/somaxconn # moved to bin/run.sh due to "Read-only filesystem error"

CMD ["/bin/run.sh"]
