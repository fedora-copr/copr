FROM registry.fedoraproject.org/fedora:43
MAINTAINER copr-devel@lists.fedorahosted.org

ARG ADDITIONAL_COPR_REPOSITORIES="@copr/copr-dev"

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux

# base packages
RUN set -ex ; \
    test -z "${ADDITIONAL_COPR_REPOSITORIES}" \
        || dnf -y install dnf-plugins-core \
        && for repo in $ADDITIONAL_COPR_REPOSITORIES ; do dnf -y copr enable $repo; done ; \
    dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
# builder packages
                   openssh-server \
                   fedora-packager \
                   mock \
                   mock-lvm \
                   createrepo \
                   yum-utils \
                   rsync \
                   openssh-clients \
                   rpm \
                   glib2 \
                   ca-certificates \
                   ethtool \
    && dnf -y install copr-builder \
    && dnf clean all

COPY files/ /

# Only runtime-mounted public keys may authenticate.  Host keys are generated
# at startup so they are unique to each container, never part of an image layer.
RUN mkdir -p /root/.ssh /run/sshd && \
    chmod 700 /root /root/.ssh

RUN echo 'config_opts["use_nspawn"] = False' >> /etc/mock/site-defaults.cfg

ENTRYPOINT ["/entrypoint"]
CMD ["/usr/sbin/sshd", "-D", "-e"]
