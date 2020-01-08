FROM fedora:30
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
                   copr-selinux \
                   cgit \
                   tito

COPY . /copr

RUN cd /copr/dist-git && \
    dnf builddep -y *spec && \
    tito build --rpm --test --rpmbuild-options='--nocheck' && \
    ( dnf -y install /tmp/tito/noarch/copr-dist-git*.noarch.rpm || true ) && \
    dnf clean all

RUN rm /etc/httpd/conf.d/ssl.conf

RUN echo "AliasMatch \"/repo(/.*)/md5(/.*)\" \"/var/lib/dist-git/cache/lookaside\\$1\\$2\"" >> /etc/httpd/conf.d/dist-git/lookaside-copr.conf && \
    echo "Alias /repo/ /var/lib/dist-git/cache/lookaside/" >>  /etc/httpd/conf.d/dist-git/lookaside-copr.conf

CMD ["/usr/sbin/httpd", "-DFOREGROUND"]
