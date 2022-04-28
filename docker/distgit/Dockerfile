FROM registry.fedoraproject.org/fedora:35
MAINTAINER copr-devel@lists.fedorahosted.org

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux
ENV PYTHONPATH=/usr/share/copr/

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   which \
                   wget \
                   vim \
                   cgit \
                   python3-rpkg \
                   python3-ipdb

RUN dnf -y install copr-dist-git && \
    dnf clean all

RUN mkdir /tmp/copr-dist-git
RUN chown copr-dist-git:packager /tmp/copr-dist-git

RUN echo "[dist-git]" > /etc/copr/copr-dist-git.conf && \
    echo "frontend_base_url=http://frontend:5000" >> /etc/copr/copr-dist-git.conf && \
    echo "frontend_auth=1234"  >> /etc/copr/copr-dist-git.conf && \
    chmod 644 /etc/copr/copr-dist-git.conf

RUN echo " [user]" >> /home/copr-dist-git/.gitconfig && \
    echo " email = copr-devel@lists.fedorahosted.org" >> /home/copr-dist-git/.gitconfig && \
    echo " name = Copr dist git" >> /home/copr-dist-git/.gitconfig && \
    chown copr-dist-git:copr-dist-git /home/copr-dist-git/.gitconfig

RUN sed -i "s/^cache-size.*//" /etc/cgitrc
RUN echo 'scan-path=/var/lib/dist-git/git/rpms' | tee -a /etc/cgitrc

CMD ["/usr/sbin/runuser", "-u", "root", "-g", "packager", "/usr/bin/importer_runner.py"]
