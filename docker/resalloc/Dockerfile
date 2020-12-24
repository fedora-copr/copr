FROM fedora:33
MAINTAINER copr-devel@lists.fedorahosted.org

# Deployment instructions are described here
# https://github.com/praiskup/resalloc/blob/master/docs/start-resalloc-server.txt
#
# Copr production deployment is described here
# https://pagure.io/fedora-infra/ansible/blob/master/f/roles/copr/backend/tasks/resalloc.yml

RUN dnf install -y vim \
                   resalloc \
                   resalloc-server \
                   sqlite \
                   openssh-clients

# copy filesystem setup
COPY files/ /

RUN cd /usr/lib/python3.9/site-packages/resallocserver && alembic-3 upgrade head
