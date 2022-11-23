FROM registry.fedoraproject.org/fedora:37
ARG COPR_PACKAGES=devel
MAINTAINER copr-devel@lists.fedorahosted.org
ENV container docker

RUN dnf -y update \
    && dnf -y install dnf-plugins-core wget \
    && dnf -y copr enable @copr/copr \
    && if test "$COPR_PACKAGES" = devel; then dnf -y copr enable @copr/copr-dev; fi \
    && dnf -y install hostname htop net-tools iputils vim mlocate git sudo \
              openssh-server psmisc python-jedi procps-ng findutils tmux \
              expect python3-behave python3-hamcrest \
    && dnf -y install python3-copr rpm-build copr-cli jq \
    && dnf -y install beakerlib \
    && dnf -y clean all

RUN for repo in fedora updates updates-testing; do \
    dnf -y config-manager --save --setopt $repo.excludepkgs=hello ; done

RUN echo "LANG=en_US.UTF-8" >> /etc/locale
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

RUN echo 'root:passwd' | chpasswd
RUN echo 'export LANG=en_US.UTF-8' >> /root/.bashrc
RUN echo 'set -g history-limit 40960' > /root/.tmux.conf

COPY bashrc /root/.bashrc_copr

RUN echo "source /root/.bashrc_copr" >> /root/.bashrc

RUN echo -e "[tested-copr]\nhostname = copr.stg.fedoraproject.org\nprotocol = https\nport = 443\n" \
    >  /etc/dnf/plugins/copr.d/tested-copr.conf

# Run this container with -ti to avoid an immediate shutdown!
CMD ["/bin/bash"]
