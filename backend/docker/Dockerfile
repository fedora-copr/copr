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
RUN dnf -y install nginx

# builder packages
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

# packages for copr-keygen
RUN dnf -y install uwsgi
RUN dnf -y install uwsgi-plugin-python

# needed to be able to ping
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

# needed to run sshd
RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

# setup root user
RUN echo 'root:passwd' | chpasswd
RUN mkdir /root/.ssh &&  chmod 700 /root /root/.ssh
RUN touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys
RUN ssh-keygen -f /root/.ssh/id_rsa -N '' -q -C root@locahost
RUN cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys

# setup copr user
RUN useradd copr
RUN echo 'copr:passwd' | chpasswd
RUN echo 'copr ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers
RUN mkdir -p /home/copr/.ssh && chmod 700 /home/copr /home/copr/.ssh
RUN ssh-keygen -f /home/copr/.ssh/id_rsa -N '' -q -C copr@locahost
RUN touch /home/copr/.ssh/authorized_keys && chmod 600 /home/copr/.ssh/authorized_keys
RUN cat /home/copr/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys
RUN cat /home/copr/.ssh/id_rsa.pub >> /home/copr/.ssh/authorized_keys
RUN chown copr:copr -R /home/copr

# setup user for web access
RUN useradd -r apache

# decides if we should install released or latest (git) versions of COPR packages
ARG RELEASETEST

# enable appropriate copr repos
RUN dnf -y copr enable @copr/copr
RUN dnf -y copr enable @modularity/modulemd
RUN if [ ! $RELEASETEST ]; then dnf -y copr enable @copr/copr-dev; fi

# additional builder packages from COPR repos
RUN dnf -y install fedpkg-copr

# preinstall copr-keygen and its builddeps to utilize most of Docker cache
RUN cd `mktemp -d` && dnf -y download --source copr-keygen && dnf -y builddep *.src.rpm --allowerasing
RUN dnf -y install copr-keygen

# system setup for copr-keygen
RUN mkdir /var/log/uwsgi
RUN chown apache:apache /var/log/uwsgi
RUN chmod 775 /var/log/uwsgi
RUN chown apache:apache /var/run/uwsgi
RUN chmod 775 /var/run/uwsgi
RUN usermod copr-signer -G apache

# preinstall backend and its builddeps to utilize most of Docker cache
RUN cd `mktemp -d` && dnf -y download --source copr-backend && dnf -y builddep *.src.rpm --allowerasing
RUN dnf -y install copr-backend

# system setup for copr-backend
RUN usermod -a -G mock copr

# copy your copr sources to the docker image
COPY . /copr

# build copr-backend from sources
RUN dnf -y builddep /copr/backend/copr-backend.spec --allowerasing # fix for python-requests package (the cmd is failing python2-requests is already installed)
RUN cd /copr/backend && export LANG=en_US.UTF-8 && if [ ! $RELEASETEST ]; then tito build --test --rpm; else tito build --rpm; fi
RUN dnf -y install /tmp/tito/noarch/copr-backend*.noarch.rpm

# build copr-keygen from sources
RUN dnf -y builddep /copr/keygen/copr-keygen.spec --allowerasing
RUN cd /copr/keygen && export LANG=en_US.UTF-8 && if [ ! $RELEASETEST ]; then tito build --test --rpm; else tito build --rpm; fi
RUN dnf -y install /tmp/tito/noarch/copr-keygen*.noarch.rpm

# copy filesystem setup and setup ownership and permissions
COPY backend/docker/files/ /
RUN chmod 700 /root && chmod 700 /home/copr && chown copr:copr /home/copr
RUN chown copr-signer:apache /etc/uwsgi.d/copr-keygen.ini
# fix permissions on /var/log/copr-keygen/main.log which is
# owned by root after copr-keygen installation tests are run
RUN chown copr-signer:copr-signer /var/log/copr-keygen/main.log

# workarounds
RUN dnf -y downgrade fedpkg # temporary fix cause fedpkg-copr doesn't work with the new version of fedpkg
RUN dnf -y install ansible1.9 --allowerasing # copr does not support ansible2 yet

CMD ["/bin/run.sh"]
