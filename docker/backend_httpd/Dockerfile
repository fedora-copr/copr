FROM fedora/nginx

MAINTAINER copr-devel@lists.fedorahosted.org

# Stop listening on port 80 (taken by dist-git).  We don't need the port 666
# here, but we need to use something for the sake of config "patching"
# simplicity.
RUN sed -i  's/80 /666 /' /etc/nginx/nginx.conf

COPY files/ /
