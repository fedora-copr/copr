FROM fedora:28
MAINTAINER jkadlcik@redhat.com

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
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
                   rpkg

COPY . /copr
COPY docker/frontend/files/ /

# build and install copr-frontend
RUN rm -rf /tmp/rpkg && \
    rpkg --path /copr/frontend srpm --without doc --without check --outdir /tmp/rpkg && \
    dnf -y builddep /tmp/rpkg/copr-frontend*.src.rpm && \
    rpkg --path /copr/frontend local --without doc --without check --outdir /tmp/rpkg && \
    dnf -y install /tmp/rpkg/noarch/copr-frontend*.noarch.rpm

RUN echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

CMD ["/bin/run.sh"]
