FROM registry.fedoraproject.org/fedora:41
MAINTAINER copr-devel@lists.fedorahosted.org

# Deployment instructions are described here
# https://github.com/praiskup/resalloc/blob/master/docs/start-resalloc-server.txt
#
# Copr production deployment is described here
# https://pagure.io/fedora-infra/ansible/blob/master/f/roles/copr/backend/tasks/resalloc.yml

RUN dnf install -y ansible \
                   vim \
                   resalloc \
                   resalloc-aws \
                   resalloc-server \
                   resalloc-webui \
                   sqlite \
                   findutils \
                   openssh-clients \
    && dnf clean all

# copy filesystem setup
COPY files/ /

CMD cd $(rpm -ql resalloc-server |grep alembic.ini |xargs dirname) \
    && alembic-3 upgrade head \
    && /usr/bin/resalloc-server
