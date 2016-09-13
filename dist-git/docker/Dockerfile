FROM fedora:24
MAINTAINER clime@redhat.com

RUN dnf -y install mock-scm
RUN dnf -y install tito
RUN dnf -y install pyp2rpm
RUN dnf -y install rubygem-gem2rpm

# source image contains only C/POSIX locales:
# https://github.com/fedora-cloud/docker-brew-fedora/issues/39
RUN truncate /etc/rpm/macros.image-language-conf --size=0
RUN dnf -y reinstall glibc-all-langpacks # hacky workaround

CMD ["/bin/sh"]
