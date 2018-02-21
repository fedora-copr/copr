FROM fedora:26
MAINTAINER jkadlcik@redhat.com


# base packages
# ad. python-alembic: https://bugzilla.redhat.com/show_bug.cgi?id=1536058
RUN dnf -y update && \
    dnf -y install dnf-plugins-core \
                   htop \
                   which \
                   tito \
                   wget \
                   vim \
                   yum \
                   supervisor \
                   copr-selinux \
                   python-alembic \
                   python3-alembic \
                   postgresql-server \
                   redis

RUN dnf -y copr enable @copr/copr
RUN dnf -y copr enable @modularity/modulemd

COPY . /copr
COPY docker/frontend/files/ /


# Install build dependencies for Copr Frontend
RUN dnf -y builddep /copr/frontend/copr-frontend.spec

# Remove previous build, if any
RUN rm -rf /tmp/tito

# Build Copr Frontend
RUN cd /copr/frontend/ && tito build --test --rpm --rpmbuild-options='--nocheck --without doc'

# Install the Copr Frontend build
RUN dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm

RUN echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

CMD ["/bin/run.sh"]
