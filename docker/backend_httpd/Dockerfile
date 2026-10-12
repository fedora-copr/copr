# https://github.com/sclorg/nginx-container
FROM quay.io/sclorg/nginx-126-c10s

MAINTAINER copr-devel@lists.fedorahosted.org

COPY files/etc/nginx/conf.d/copr-be.conf /opt/app-root/etc/nginx.d/copr-be.conf

EXPOSE 5002

CMD ["nginx", "-g", "daemon off;"]
