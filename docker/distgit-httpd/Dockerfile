FROM registry.fedoraproject.org/fedora:35
MAINTAINER copr-devel@lists.fedorahosted.org

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux

# For copr-common
RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
                   cgit

RUN dnf -y install copr-dist-git && \
    dnf clean all

RUN rm /etc/httpd/conf.d/ssl.conf

RUN echo "AliasMatch \"/repo(/.*)/md5(/.*)\" \"/var/lib/dist-git/cache/lookaside\\$1\\$2\"" >> /etc/httpd/conf.d/dist-git/lookaside-copr.conf && \
    echo "Alias /repo/ /var/lib/dist-git/cache/lookaside/" >>  /etc/httpd/conf.d/dist-git/lookaside-copr.conf

CMD ["/usr/sbin/httpd", "-DFOREGROUND"]
