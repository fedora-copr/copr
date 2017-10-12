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
                   copr-selinux \
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
RUN cd /copr/frontend/ && tito build --test --rpm --rpmbuild-options='--nocheck'

# Install the Copr Frontend build
RUN dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm

# Configure dist git url
RUN sed -i.bak -e "s/^DIST_GIT_URL.*/DIST_GIT_URL = 'http:\\/\\/distgit\\/cgit\\/'/g" /etc/copr/copr.conf
RUN sed -i.bak -e "s/^DIST_GIT_CLONE_URL.*/DIST_GIT_CLONE_URL = 'http:\\/\\/distgit\\/git\\/'/g" /etc/copr/copr.conf

# Configure backend base url
RUN sed -i.bak -e "s/^BACKEND_BASE_URL.*/BACKEND_BASE_URL = 'http:\\/\\/backend:5002'/g" /etc/copr/copr.conf

# Configure backend password
RUN sed -i.bak -e "s/^#BACKEND_PASSWORD.*/BACKEND_PASSWORD = \\'1234\\'/g" /etc/copr/copr.conf

# Configure import logs url
RUN sed -i.bak -e "s/^COPR_DIST_GIT_LOGS_URL.*/COPR_DIST_GIT_LOGS_URL = 'http:\\/\\/distgit\\/per-task-logs'/g" /etc/copr/copr.conf



CMD ["/bin/run.sh"]
