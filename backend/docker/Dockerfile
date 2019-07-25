FROM fedora:30
MAINTAINER copr-devel@lists.fedorahosted.org

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
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
                   fedora-packager \
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
                   uwsgi-plugin-python3 \
# to get more entropy for generation of gpg keys
                   rng-tools \
# for unbuffer package
                   expect \
                   rpkg

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

# preinstall rpmbuild and its builddeps to utilize most of Docker cache
RUN cd `mktemp -d` && \
    dnf -y download --source copr-rpmbuild && \
    dnf -y builddep *.src.rpm --allowerasing && \
    dnf -y install copr-rpmbuild && \
    dnf clean all

# copy your copr sources to the docker image
COPY . /copr

# build copr-backend from sources
RUN rpkg --path /copr/backend spec --outdir /tmp/rpkg && \
    dnf -y builddep /tmp/rpkg/copr-backend.spec --allowerasing && \
    export LANG=en_US.UTF-8 && \
    rpkg --path /copr/backend local --outdir /tmp/rpkg && \
# upgrade the already pre-installed package if possible
    dnf -y upgrade /tmp/rpkg/noarch/copr-backend*.noarch.rpm || true

# build copr-keygen from sources
RUN rpkg --path /copr/keygen spec --outdir /tmp/rpkg && \
    dnf -y builddep /tmp/rpkg/copr-keygen.spec --allowerasing && \
    export LANG=en_US.UTF-8 && \
    rpkg --path /copr/keygen local --outdir /tmp/rpkg && \
# upgrade the already pre-installed package if possible
    dnf -y upgrade /tmp/rpkg/noarch/copr-keygen*.noarch.rpm || true

# build copr-rpmbuild from sources
RUN rpkg --path /copr/rpmbuild spec --outdir /tmp/rpkg && \
    dnf -y builddep /tmp/rpkg/copr-rpmbuild.spec --allowerasing && \
    export LANG=en_US.UTF-8 && \
    rpkg --path /copr/rpmbuild local --outdir /tmp/rpkg && \
# upgrade the already pre-installed package if possible
    dnf -y upgrade /tmp/rpkg/noarch/copr-rpmbuild*.noarch.rpm || true

# copy filesystem setup and setup ownership and permissions
COPY backend/docker/files/ /
RUN chmod 700 /root && \
    chmod 700 /home/copr && \
    chown copr:copr /home/copr && \
    chown copr-signer:apache /etc/uwsgi.d/copr-keygen.ini && \
# fix permissions on /var/log/copr-keygen/main.log which is
# owned by root after copr-keygen installation tests are run
    chown copr-signer:copr-signer /var/log/copr-keygen/main.log || true

CMD ["/bin/run.sh"]
