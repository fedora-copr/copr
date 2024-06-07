FROM registry.fedoraproject.org/fedora:39

MAINTAINER copr-devel@lists.fedorahosted.org

ARG ADDITIONAL_COPR_REPOSITORIES="@mock/mock-stable"

# Create copr-signer:copr-signer manually, so we can
# be sure that the UID and GID is same on all keygen containers
RUN groupadd -r copr-signer -g 992
RUN useradd -r copr-signer -u 993 -g 992 -G 0 -d /var/lib/copr-keygen

# base packages
RUN set -ex ; \
    test -z "${ADDITIONAL_COPR_REPOSITORIES}" \
        || dnf -y install dnf-plugins-core \
        && for repo in $ADDITIONAL_COPR_REPOSITORIES ; do dnf -y copr enable $repo; done ; \
    dnf -y update && \
    dnf -y install htop \
                   httpd \
                   make \
                   which \
                   wget \
                   vim \
                   yum \
                   sudo \
                   python3-alembic \
                   postgresql-server \
                   redis \
                   tini \
                   && \
    && dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-39.noarch.rpm https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-39.noarch.rpm -y \
    && dnf install mock-rpmfusion-nonfree -y \
    && sed -i 's|epel-9-x86_64.cfg|alma+epel-9-x86_64.cfg|' /etc/mock/epel+rpmfusion_free-9-x86_64.cfg \
    && sed -i 's|epel-8-x86_64.cfg|alma+epel-8-x86_64.cfg|' /etc/mock/epel+rpmfusion_free-8-x86_64.cfg \
    && cat /etc/mock/epel-next-9-x86_64-rpmfusion_free.cfg > /etc/mock/epel-next-8-x86_64-rpmfusion_free.cfg \
    && cat /etc/mock/epel-next-9-x86_64-rpmfusion_nonfree.cfg > /etc/mock/epel-next-8-x86_64-rpmfusion_nonfree.cfg \
    && sed -i 's|epel-next-9-x86_64.cfg|epel-next-8-x86_64.cfg|' /etc/mock/epel-next-8-x86_64-rpmfusion_free.cfg \
    && sed -i 's|epel-next+rpmfusion_free-9-x86_64.cfg|epel-next+rpmfusion_free-8-x86_64.cfg|' /etc/mock/epel-next-8-x86_64-rpmfusion_nonfree.cfg \
    dnf -y install copr-keygen && \
    dnf clean all

# Copy files from the host into the container
COPY files/ /

RUN sed -i 's/Listen 80/#Listen 80/g' /etc/httpd/conf/httpd.conf

# OpenShift runs this project as <RANDOMUID>:root
# Podman runs this as copr-signer with root in supplementary groups
RUN chmod g+rwx /var/log/httpd

# Drop the suid bit
RUN chmod 0755 /usr/bin/sign

# entrypoint needs to have write access here (group=0)
RUN chown copr-signer:root /etc/sign.conf && \
    chmod 0660 /etc/sign.conf

# TODO: we should just check for non-root accounts
RUN sed -i "s|getpass.getuser() != 'copr-signer'|False|" /usr/bin/gpg-copr

RUN dirs="/var/run/signd /var/run/httpd" ; \
    for dir in $dirs; do \
      mkdir -p "$dir" && \
      chown root:root "$dir" && \
      chmod 0770 "$dir" ; \
    done

USER copr-signer

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/usr/sbin/httpd", "-DFOREGROUND"]
