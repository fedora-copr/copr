FROM fedora:25
MAINTAINER clime@redhat.com

RUN dnf -y install tito \
                   pyp2rpm \
                   rubygem-gem2rpm \
                   mock mock-scm \
                   git-annex which

ENV LANG en_US.UTF-8

CMD ["/bin/sh"]
