FROM fedora:26
MAINTAINER jkadlcik@redhat.com

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
                   yum \
                   supervisor \
                   copr-selinux \
                   python3-alembic \
                   postgresql-server \
                   redis \
                   rpkg

COPY . /copr
COPY docker/frontend/files/ /

# build and install copr-frontend
RUN rm -rf /tmp/rpkg && \
    echo '%with() %{expand:%%{?with_%{1}:0}%%{!?with_%{1}:0}}' >> ~/.rpmmacros && \
    rpkg --path /copr/frontend spec --outdir /tmp/rpkg && \
    dnf -y builddep /tmp/rpkg/copr-frontend.spec && \
    rpkg --path /copr/frontend local --outdir /tmp/rpkg && \
    dnf -y install /tmp/rpkg/noarch/copr-frontend*.noarch.rpm

RUN echo 'nameserver 8.8.8.8' | tee -a /etc/resolv.conf

CMD ["/bin/run.sh"]
