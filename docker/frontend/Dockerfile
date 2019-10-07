FROM fedora:30
MAINTAINER copr-devel@lists.fedorahosted.org

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   make \
                   which \
                   wget \
                   vim \
                   yum \
                   sudo \
                   supervisor \
                   copr-selinux \
                   python3-alembic \
                   postgresql-server \
                   redis \
                   tito

COPY . /copr
COPY docker/frontend/files/ /

# build and install copr-frontend
RUN cd /copr/frontend && \
    dnf builddep -y *spec && \
    tito build --rpm --test --rpmbuild-options='--nocheck' && \
    ( dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm || true ) && \
    dnf clean all

RUN echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

CMD ["/bin/run.sh"]
