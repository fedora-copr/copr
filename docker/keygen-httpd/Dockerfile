FROM registry.fedoraproject.org/fedora:35

MAINTAINER copr-devel@lists.fedorahosted.org


# Create copr-signer:copr-signer manually, so we can
# be sure that the UID and GID is same on all keygen containers
RUN groupadd -r copr-signer -g 992
RUN useradd -r copr-signer -u 993 -g 992 -d /var/lib/copr-keygen

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   httpd \
                   make \
                   which \
                   wget \
                   vim \
                   yum \
                   sudo \
                   supervisor \
                   python3-alembic \
                   postgresql-server \
                   redis \
                   && \
    dnf -y install copr-keygen && \
    dnf clean all

# system setup for copr-keygen
RUN mkdir /var/log/uwsgi /var/run/uwsgi && \
    chown apache:apache /var/log/uwsgi && \
    chmod 775 /var/log/uwsgi && \
    chown apache:apache /var/run/uwsgi && \
    chmod 775 /var/run/uwsgi && \
    usermod copr-signer -G apache

# Copy files from the host into the container
COPY files/ /

RUN sed -i 's/Listen 80/#Listen 80/g' /etc/httpd/conf/httpd.conf

CMD ["/entrypoint"]
