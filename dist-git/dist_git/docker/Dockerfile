FROM fedora:25
MAINTAINER clime@redhat.com

RUN dnf -y install tito \
                   pyp2rpm \
                   rubygem-gem2rpm \
                   mock mock-scm \
                   git-annex which

# ensure all possible locales are installed
RUN truncate /etc/rpm/macros.image-language-conf --size=0
RUN dnf -y reinstall glibc-all-langpacks || dnf -y install glibc-all-langpacks --best \
    dnf clean all

ENV LANG en_US.UTF-8

CMD ["/bin/sh"]
