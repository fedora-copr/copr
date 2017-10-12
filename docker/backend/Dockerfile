FROM fedora:26
MAINTAINER clime@redhat.com

# base packages
RUN dnf -y update && \
    dnf -y install dnf-plugins-core \
                   htop \
                   tito \
                   wget \
                   net-tools \
                   iputils \
                   vim \
                   mlocate \
                   git \
                   sudo \
                   openssh-server \
                   supervisor \
                   psmisc \
                   nginx \
# builder packages
                   packagedb-cli \
                   fedora-cert \
                   mock \
                   mock-lvm \
                   createrepo \
                   yum-utils \
                   pyliblzma \
                   rsync \
                   openssh-clients \
                   libselinux-python \
                   libsemanage-python \
                   rpm \
                   glib2 \
                   ca-certificates \
                   scl-utils-build \
                   ethtool \
# packages for copr-keygen
                   uwsgi \
                   uwsgi-plugin-python \
# to get more entropy for generation of gpg keys
                   rng-tools \
# for unbuffer package
                   expect && \
    dnf clean all

# needed to be able to ping
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

# needed to run sshd
RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

# setup root user
RUN echo 'root:passwd' | chpasswd && \
    mkdir /root/.ssh &&  chmod 700 /root /root/.ssh && \
    touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && \
    ssh-keygen -f /root/.ssh/id_rsa -N '' -q -C root@locahost && \
    cat /root/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys

# setup copr user
RUN useradd copr && \
    echo 'copr:passwd' | chpasswd && \
    echo 'copr ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers && \
    mkdir -p /home/copr/.ssh && chmod 700 /home/copr /home/copr/.ssh && \
    ssh-keygen -f /home/copr/.ssh/id_rsa -N '' -q -C copr@locahost && \
    touch /home/copr/.ssh/authorized_keys && chmod 600 /home/copr/.ssh/authorized_keys && \
    cat /home/copr/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && \
    cat /home/copr/.ssh/id_rsa.pub >> /home/copr/.ssh/authorized_keys && \
    chown copr:copr -R /home/copr

# setup user for web access
RUN useradd -r apache

# decides if we should install released or latest (git) versions of COPR packages
ARG RELEASETEST

# enable appropriate copr repos
RUN dnf -y copr enable @copr/copr && \
    dnf -y copr enable @modularity/modulemd && \
    if [ ! $RELEASETEST ]; then dnf -y copr enable @copr/copr-dev; fi

# additional builder packages from COPR repos
RUN dnf -y install copr-rpmbuild && dnf clean all

# preinstall copr-keygen and its builddeps to utilize most of Docker cache
RUN cd `mktemp -d` && dnf -y download --source copr-keygen && \
    dnf -y builddep *.src.rpm --allowerasing && \
    dnf -y install copr-keygen && \
    dnf clean all

# system setup for copr-keygen
RUN mkdir /var/log/uwsgi && \
    chown apache:apache /var/log/uwsgi && \
    chmod 775 /var/log/uwsgi && \
    chown apache:apache /var/run/uwsgi && \
    chmod 775 /var/run/uwsgi && \
    usermod copr-signer -G apache

# preinstall backend and its builddeps to utilize most of Docker cache
RUN cd `mktemp -d` && \
    dnf -y download --source copr-backend && \
    dnf -y builddep *.src.rpm --allowerasing && \
    dnf -y install copr-backend && \
    dnf clean all

# system setup for copr-backend
RUN usermod -a -G mock copr

# copy your copr sources to the docker image
COPY . /copr

# build copr-backend from sources
# fix for python-requests package (the cmd is failing python2-requests is already installed)
RUN dnf -y builddep /copr/backend/copr-backend.spec --allowerasing && \
    cd /copr/backend && \
    export LANG=en_US.UTF-8 && \
    if [ ! $RELEASETEST ]; then \
        tito build --test --rpm; \
    else \
        tito build --rpm; \
    fi && \
# upgrade the already pre-installed package if possible
    dnf -y upgrade /tmp/tito/noarch/copr-backend*.noarch.rpm || true && \
# build copr-keygen from sources
    dnf -y builddep /copr/keygen/copr-keygen.spec --allowerasing && \
    cd /copr/keygen && \
    export LANG=en_US.UTF-8 && \
    if [ ! $RELEASETEST ]; then \
        tito build --test --rpm; \
    else \
        tito build --rpm; \
    fi && \
# upgrade the already pre-installed package if possible
    dnf -y upgrade /tmp/tito/noarch/copr-keygen*.noarch.rpm || true && \
    dnf clean all

# copy filesystem setup and setup ownership and permissions
COPY docker/backend/files/ /
RUN chmod 700 /root && \
    chmod 700 /home/copr && \
    chown copr:copr /home/copr && \
    chown copr-signer:apache /etc/uwsgi.d/copr-keygen.ini && \
# fix permissions on /var/log/copr-keygen/main.log which is
# owned by root after copr-keygen installation tests are run
    chown copr-signer:copr-signer /var/log/copr-keygen/main.log

# fix permissions for .ssh
RUN chmod 700 /root/.ssh

CMD ["/bin/run.sh"]
