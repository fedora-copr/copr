FROM registry.fedoraproject.org/fedora:39
MAINTAINER copr-devel@lists.fedorahosted.org


ARG ADDITIONAL_COPR_REPOSITORIES="@mock/mock-stable"

# Deployment instructions are described here
# https://github.com/praiskup/resalloc/blob/master/docs/start-resalloc-server.txt
#
# Copr production deployment is described here
# https://pagure.io/fedora-infra/ansible/blob/master/f/roles/copr/backend/tasks/resalloc.yml

RUN RUN set -ex ; \
    test -z "${ADDITIONAL_COPR_REPOSITORIES}" \
        || dnf -y install dnf-plugins-core \
        && for repo in $ADDITIONAL_COPR_REPOSITORIES ; do dnf -y copr enable $repo; done ; \
    dnf -y update && \
    dnf install -y ansible \
                   vim \
                   resalloc \
                   resalloc-aws \
                   resalloc-server \
                   sqlite \
                   findutils \
                   openssh-clients \
    && dnf install https://mirrors.rpmfusion.org/free/fedora/rpmfusion-free-release-39.noarch.rpm https://mirrors.rpmfusion.org/nonfree/fedora/rpmfusion-nonfree-release-39.noarch.rpm -y \
    && dnf install mock-rpmfusion-nonfree -y \
    && sed -i 's|epel-next-9-x86_64.cfg|alma+epel-9-x86_64.cfg|' /etc/mock/epel-next+rpmfusion_free-9-x86_64.cfg \
    && sed -i 's|epel-next-8-x86_64.cfg|alma+epel-8-x86_64.cfg|' /etc/mock/epel-next+rpmfusion_free-8-x86_64.cfg \
    && dnf clean all

# copy filesystem setup
COPY files/ /

RUN cd $(rpm -ql resalloc-server |grep alembic.ini |xargs dirname) \
    && alembic-3 upgrade head
