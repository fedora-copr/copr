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

COPY docker/database/files/ /

CMD ["/bin/run.sh"]
