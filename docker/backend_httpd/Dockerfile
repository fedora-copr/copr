FROM registry.fedoraproject.org/fedora:43

MAINTAINER copr-devel@lists.fedorahosted.org

RUN dnf -y install nginx \
    && dnf clean all

COPY files/etc/nginx/conf.d/copr-be.conf /etc/nginx/conf.d/copr-be.conf

# Serve the results volume, and stay compatible with OpenShift's
# restricted SCC (random UID, group 0).
RUN mkdir -p /var/lib/copr/public_html \
    && chown -R root:root /var/lib/copr /var/log/nginx /var/lib/nginx /run \
    && chmod -R g+rwX /var/lib/copr /var/log/nginx /var/lib/nginx /run

USER 987
EXPOSE 5002

CMD ["nginx", "-g", "daemon off;"]
