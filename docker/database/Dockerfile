FROM fedora:28
MAINTAINER jkadlcik@redhat.com

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
                   supervisor \
                   copr-selinux \
                   postgresql-server \
                   redis

COPY docker/database/files/ /

RUN runuser -l postgres -c "initdb -E UTF8 -D /var/lib/pgsql/data"

RUN echo "listen_addresses = '*'" >> /var/lib/pgsql/data/postgresql.conf

# I want to prepend some lines to a file - I'll do it in three steps
# 1.  backup the database config file
RUN mv /var/lib/pgsql/data/pg_hba.conf /tmp/pg_hba.conf

# 2.  write the lines
RUN printf 'local coprdb copr-fe md5\nhost  coprdb copr-fe 127.0.0.1/8 md5\nhost  coprdb copr-fe ::1/128 md5\nlocal coprdb postgres  ident\nhost  coprdb copr-fe 172.18.0.0/12 md5\n' | tee /var/lib/pgsql/data/pg_hba.conf

# 3.  write the file back after those lines
RUN cat /tmp/pg_hba.conf | tee -a  /var/lib/pgsql/data/pg_hba.conf

CMD ["/bin/run.sh"]
