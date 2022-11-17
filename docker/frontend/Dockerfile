FROM registry.fedoraproject.org/fedora:37
MAINTAINER copr-devel@lists.fedorahosted.org

ARG ADDITIONAL_COPR_REPOSITORIES="@copr/copr-dev"

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux
ENV LANG=en_US.UTF-8
ENV REDIS_HOST=redis

# base packages
RUN set -ex ; \
    test -z "${ADDITIONAL_COPR_REPOSITORIES}" \
        || dnf -y install dnf-plugins-core \
        && for repo in $ADDITIONAL_COPR_REPOSITORIES ; do dnf -y copr enable $repo; done ; \
    dnf -y update && \
    dnf -y install htop \
                   make \
                   which \
                   wget \
                   vim \
                   yum \
                   sudo \
                   python3-alembic \
                   python3-ipdb \
                   python3-anytree \
                   postgresql-server \
                   redis \
                   mock-core-configs \
                   findutils \
                   copr-frontend \
                   modulemd-tools \
    && dnf clean all

COPY files/ /

RUN sed -i 's/User apache/User copr-fe/g' /etc/httpd/conf/httpd.conf
RUN sed -i 's/Group apache/Group copr-fe/g' /etc/httpd/conf/httpd.conf

# We cannot expose privileged port as non-root user
RUN sed -i 's/Listen 80/#Listen 80/g' /etc/httpd/conf/httpd.conf

# Otherwise it is run/httpd.pid in OpenShift, which is outside of
# the copr-fe user permissions
RUN echo "PidFile /var/run/httpd/httpd.pid" >> /etc/httpd/conf/httpd.conf

# Configuration based on environment variables
RUN sed -i "s/REDIS_HOST = \"redis\"/REDIS_HOST = \"${REDIS_HOST}\"/g" /etc/copr/copr.conf

# Some OpenShift shenanigans
# We can't have these directories owned by copr-fe:copr-fe
# because OpenShift runs pod as a semi-randomly generated user
# https://docs.openshift.com/container-platform/4.3/openshift_images/create-images.html#use-uid_create-images
RUN chown -R copr-fe:root \
    /usr/share/copr \
    /var/log/copr-frontend \
    /etc/httpd/ \
    /var/run/httpd/ \
    /var/log/httpd/

# Too bad, Dockerfile can't handle arrays in ARG definitions
# so we need to copy-paste the directories
RUN chmod -R g+rwX \
    /usr/share/copr \
    /var/log/copr-frontend \
    /etc/httpd/ \
    /var/run/httpd/ \
    /var/log/httpd/

# Use copr-fe user when running outside of OpenShift
USER copr-fe

# Since home directory for `copr-fe` user is `/usr/share/copr/coprs_frontend`
# and we don't want .bashrc file in there, the bash prompt is `bash-5.0$` which
# looks bad in copy-pasted outputs and tutorials. I borrowed this one from
# /root/.bashrc
ENV PS1="[\u@\h \W]\$ "

EXPOSE 5000

CMD ["/entrypoint"]
