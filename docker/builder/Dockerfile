FROM fedora:30
MAINTAINER copr-devel@lists.fedorahosted.org

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
                   supervisor \
# builder packages
                   openssh-server \
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
                   rpkg

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

RUN rm -rf /tmp/rpkg/* && \
    rpkg --path /copr/rpmbuild spec --outdir /tmp/rpkg && \
    dnf builddep -y /tmp/rpkg/copr-rpmbuild.spec && \
    rpkg --path /copr/rpmbuild local --outdir /tmp/rpkg && \
    dnf -y install /tmp/rpkg/x86_64/copr-rpmbuild*.x86_64.rpm

RUN echo 'config_opts["use_nspawn"] = False' >> /etc/mock/site-defaults.cfg

CMD ["/bin/run.sh"]
