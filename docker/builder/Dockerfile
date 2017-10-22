FROM fedora:26
MAINTAINER jkadlcik@redhat.com


# base packages
RUN dnf -y update && \
    dnf -y install dnf-plugins-core \
                   htop \
                   which \
                   tito \
                   wget \
                   vim \
                   supervisor \
# builder packages
                   copr-rpmbuild \
                   openssh-server \
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
                   ethtool && \
    dnf clean all

RUN dnf -y copr enable @copr/copr

# upgrade rpkg, otherwise an outdated 0.8 version is installed
RUN dnf -y upgrade rpkg && \
    dnf clean all

COPY . /copr
COPY docker/builder/files/ /
COPY docker/backend/files/root/.ssh/id_rsa.pub /root/.ssh/id_backend.pub

# needed to run sshd
RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

# setup root user
RUN echo 'root:passwd' | chpasswd && \
    chmod 700 /root /root/.ssh && \
    touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && \
    cat /root/.ssh/id_backend.pub >> /root/.ssh/authorized_keys


RUN dnf builddep -y /copr/rpmbuild/copr-rpmbuild.spec && dnf clean all

RUN rm -rf /tmp/tito/*
RUN cd /copr/rpmbuild/ && tito build --test --rpm --rpmbuild-options='--nocheck'
RUN dnf -y install /tmp/tito/noarch/copr-rpmbuild*.noarch.rpm || dnf -y upgrade /tmp/tito/noarch/copr-rpmbuild*.noarch.rpm || dnf -y downgrade /tmp/tito/noarch/copr-rpmbuild*.noarch.rpm


RUN echo 'config_opts["use_nspawn"] = False' >> /etc/mock/site-defaults.cfg


CMD ["/bin/run.sh"]
