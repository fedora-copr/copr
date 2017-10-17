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
                   cgit \
                   pyrpkg

RUN dnf -y copr enable @copr/copr
RUN dnf -y copr enable clime/dist-git

COPY . /copr
COPY docker/distgit/files/ /


RUN dnf builddep -y /copr/dist-git/copr-dist-git.spec

RUN rm -rf /tmp/tito/*
RUN cd /copr/dist-git/ && tito build --test --rpm --rpmbuild-options='--nocheck'
RUN dnf -y install /tmp/tito/noarch/copr-dist-git*.noarch.rpm || dnf -y upgrade /tmp/tito/noarch/copr-dist-git*.noarch.rpm || dnf -y downgrade /tmp/tito/noarch/copr-dist-git*.noarch.rpm

RUN mkdir /tmp/copr-dist-git
RUN chown copr-dist-git:packager /tmp/copr-dist-git

RUN echo "[dist-git]" >> /etc/copr/copr-dist-git.conf && \
    echo "frontend_base_url=http://frontend" >> /etc/copr/copr-dist-git.conf && \
    echo "frontend_auth=1234"  >> /etc/copr/copr-dist-git.conf && \
    chmod 644 /etc/copr/copr-dist-git.conf

RUN echo " [user]" >> /home/copr-dist-git/.gitconfig && \
    echo " email = copr-devel@lists.fedorahosted.org" >> /home/copr-dist-git/.gitconfig && \
    echo " name = Copr dist git" >> /home/copr-dist-git/.gitconfig && \
    chown copr-dist-git:copr-dist-git /home/copr-dist-git/.gitconfig

RUN echo "AliasMatch \"/repo(/.*)/md5(/.*)\" \"/var/lib/dist-git/cache/lookaside\\$1\\$2\"" >> /etc/httpd/conf.d/dist-git/lookaside-copr.conf && \
    echo "Alias /repo/ /var/lib/dist-git/cache/lookaside/" >>  /etc/httpd/conf.d/dist-git/lookaside-copr.conf

RUN sed -i "s/^cache-size.*//" /etc/cgitrc

RUN echo 'scan-path=/var/lib/dist-git/git/rpms' | tee -a /etc/cgitrc

CMD ["/bin/run.sh"]
