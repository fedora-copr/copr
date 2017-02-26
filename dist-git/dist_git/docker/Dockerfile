FROM fedora:25
MAINTAINER clime@redhat.com

RUN dnf -y install tito
RUN dnf -y install pyp2rpm
RUN dnf -y install rubygem-gem2rpm
RUN dnf -y install mock mock-scm

# ensure all possible locales are installed
RUN truncate /etc/rpm/macros.image-language-conf --size=0
RUN dnf -y reinstall glibc-all-langpacks || dnf -y install glibc-all-langpacks --best

ENV LANG en_US.UTF-8

CMD ["/bin/sh"]
