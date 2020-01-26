FROM fedora/apache
MAINTAINER copr-devel@lists.fedorahosted.org


# Create copr-signer:copr-signer manually, so we can
# be sure that the UID and GID is same on all keygen containers
RUN groupadd -r copr-signer -g 992
RUN useradd -r copr-signer -u 993 -g 992

# system setup for copr-keygen
RUN mkdir /var/log/uwsgi /var/run/uwsgi && \
    chown apache:apache /var/log/uwsgi && \
    chmod 775 /var/log/uwsgi && \
    chown apache:apache /var/run/uwsgi && \
    chmod 775 /var/run/uwsgi && \
    usermod copr-signer -G apache

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
                   uwsgi \
                   uwsgi-plugin-python3

# Copy files from the host into the container
COPY files/ /

# Install copr-keygen package
RUN dnf -y install copr-keygen && dnf clean all

# For whatever reason the copr-keygen package installed
# copr-signer user incorrectly and set it's home directory
# as /home/copr-signer
RUN usermod -d /usr/share/copr-keygen copr-signer

# For whatever reason, the log directory is owned by root
# and copr-signer user can't write in it
RUN chown -R copr-signer:copr-signer /var/log/copr-keygen/
