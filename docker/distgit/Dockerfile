FROM fedora:28
MAINTAINER jkadlcik@redhat.com

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
                   supervisor \
                   copr-selinux \
                   cgit \
                   python2-rpkg \
                   rpkg

COPY . /copr
COPY docker/distgit/files/ /

RUN rm -rf /tmp/rpkg/* && \
    rpkg --path /copr/dist-git spec --outdir /tmp/rpkg && \
    dnf builddep -y /tmp/rpkg/copr-dist-git.spec && \
    rpkg --path /copr/dist-git local --outdir /tmp/rpkg && \
    dnf -y install /tmp/rpkg/noarch/copr-dist-git*.noarch.rpm

RUN mkdir /tmp/copr-dist-git
RUN chown copr-dist-git:packager /tmp/copr-dist-git

RUN echo "[dist-git]" > /etc/copr/copr-dist-git.conf && \
    echo "frontend_base_url=http://frontend:5000" >> /etc/copr/copr-dist-git.conf && \
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

RUN rm /etc/httpd/conf.d/ssl.conf

CMD ["/bin/run.sh"]
