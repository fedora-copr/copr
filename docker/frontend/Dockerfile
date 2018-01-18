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
                   yum \
                   supervisor \
                   copr-selinux \
                   python-alembic \  # https://bugzilla.redhat.com/show_bug.cgi?id=1536058
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
RUN cd /copr/frontend/ && tito build --test --rpm --rpmbuild-options='--nocheck'

# Install the Copr Frontend build
RUN dnf -y install /tmp/tito/noarch/copr-frontend*.noarch.rpm

# Configure public hostname
RUN sed -i.bak -e "s/^PUBLIC_COPR_HOSTNAME.*/PUBLIC_COPR_HOSTNAME = '127.0.0.1:5000'/g" /etc/copr/copr.conf

# Configure dist git url
RUN sed -i.bak -e "s/^DIST_GIT_URL.*/DIST_GIT_URL = 'http:\\/\\/distgit\\/cgit\\/'/g" /etc/copr/copr.conf
RUN sed -i.bak -e "s/^DIST_GIT_CLONE_URL.*/DIST_GIT_CLONE_URL = 'http:\\/\\/distgit\\/git\\/'/g" /etc/copr/copr.conf

# Configure backend base url
RUN sed -i.bak -e "s/^BACKEND_BASE_URL.*/BACKEND_BASE_URL = 'http:\\/\\/backend:5002'/g" /etc/copr/copr.conf

# Configure backend password
RUN sed -i.bak -e "s/^#BACKEND_PASSWORD.*/BACKEND_PASSWORD = \\'1234\\'/g" /etc/copr/copr.conf

# Configure import logs url
RUN sed -i.bak -e "s/^COPR_DIST_GIT_LOGS_URL.*/COPR_DIST_GIT_LOGS_URL = 'http:\\/\\/distgit\\/per-task-logs'/g" /etc/copr/copr.conf

# Configure database URI
RUN sed -i.bak -e "s/^SQLALCHEMY_DATABASE_URI.*/SQLALCHEMY_DATABASE_URI = 'postgresql+psycopg2:\\/\\/copr-fe:coprpass@database\\/coprdb'/g" /etc/copr/copr.conf


RUN echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

RUN echo $'\n\
<VirtualHost 0.0.0.0>\n\
    WSGIPassAuthorization On\n\
    WSGIDaemonProcess 127.0.0.1 user=copr-fe group=copr-fe threads=5\n\
    WSGIScriptAlias / /usr/share/copr/coprs_frontend/application\n\
    WSGIProcessGroup 127.0.0.1\n\
    <Directory /usr/share/copr>\n\
        WSGIApplicationGroup %{GLOBAL}\n\
        Require all granted\n\
    </Directory>\n\
</VirtualHost>\n '\
>> /etc/httpd/conf.d/copr.conf

CMD ["/bin/run.sh"]
