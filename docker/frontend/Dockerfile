FROM fedora:30
MAINTAINER copr-devel@lists.fedorahosted.org

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux
ENV LANG=en_US.UTF-8

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

RUN echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   make \
                   which \
                   wget \
                   vim \
                   yum \
                   sudo \
                   copr-selinux \
                   python3-alembic \
                   python3-ipdb \
                   postgresql-server \
                   redis \
                   mock-core-configs \
                   tito

COPY . /copr
COPY docker/frontend/files/ /

# build and install copr-frontend
RUN cd /copr/frontend && \
    dnf builddep -y *spec && \
    tito build --rpm --test --rpmbuild-options='--nocheck' && \
    ( dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm || true ) && \
    dnf clean all

RUN mkdir -p /usr/share/copr/data/whooshee
RUN chown -R copr-fe:copr-fe /usr/share/copr
RUN chown -R copr-fe:copr-fe /var/log/copr-frontend

CMD ["/bin/run.sh"]
