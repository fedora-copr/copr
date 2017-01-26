FROM fedora:25
MAINTAINER clime@redhat.com

RUN dnf -y install tito
RUN dnf -y install pyp2rpm
RUN dnf -y install rubygem-gem2rpm
RUN dnf copr enable -y @copr/copr-dev
RUN dnf install -y mock mock-scm
RUN dnf upgrade -y mock mock-scm

# source image contains only C/POSIX locales:
# https://github.com/fedora-cloud/docker-brew-fedora/issues/39
RUN truncate /etc/rpm/macros.image-language-conf --size=0
RUN dnf -y reinstall glibc-all-langpacks # hacky workaround

ENV LANG en_US.UTF-8

CMD ["/bin/sh"]
