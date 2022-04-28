FROM registry.fedoraproject.org/fedora:35
MAINTAINER copr-devel@lists.fedorahosted.org

# Copy files from the host into the container
COPY files/ /

# Create copr-signer:copr-signer manually, so we can
# be sure that the UID and GID is same on all keygen containers
RUN groupadd -r copr-signer -g 992
RUN useradd -r copr-signer -u 993 -g 992 -d /var/lib/copr-keygen

# Install copr-keygen package
RUN dnf -y update gnupg2 && dnf -y install copr-keygen && dnf clean all

CMD ["/usr/sbin/signd"]
