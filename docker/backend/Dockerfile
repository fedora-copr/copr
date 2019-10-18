FROM fedora:30
MAINTAINER copr-devel@lists.fedorahosted.org

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr

# TERM is to make the tito work in container, rhbz#1733043
ENV TERM=linux \
    LANG=en_US.UTF-8

# base packages
RUN dnf -y update && \
    dnf -y install htop \
                   make \
                   wget \
                   net-tools \
                   iputils \
                   vim \
                   mlocate \
                   git \
                   sudo \
                   openssh-server \
                   supervisor \
                   psmisc \
                   nginx \
# to get more entropy for generation of gpg keys
                   rng-tools \
# for unbuffer package
                   expect \
                   tito && \
    dnf clean all

# needed to be able to ping
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

# needed to run sshd
RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

# setup root user
RUN echo 'root:passwd' | chpasswd && \
    mkdir /root/.ssh && chmod 700 /root /root/.ssh

# setup copr user
RUN useradd copr && \
    echo 'copr:passwd' | chpasswd && \
    echo 'copr ALL=(ALL:ALL) NOPASSWD:ALL' >> /etc/sudoers && \
    mkdir -p /home/copr/.ssh && chmod 700 /home/copr /home/copr/.ssh && \
    ssh-keygen -f /home/copr/.ssh/id_rsa -N '' -q -C copr@locahost && \
    touch /home/copr/.ssh/authorized_keys && chmod 600 /home/copr/.ssh/authorized_keys && \
    cat /home/copr/.ssh/id_rsa.pub >> /root/.ssh/authorized_keys && \
    cat /home/copr/.ssh/id_rsa.pub >> /home/copr/.ssh/authorized_keys && \
    chown copr:copr -R /home/copr


# preinstall backend and its builddeps to utilize most of Docker cache
RUN cd `mktemp -d` && \
    dnf -y download --source copr-backend && \
    dnf -y builddep *.src.rpm --allowerasing && \
    dnf -y install copr-backend && \
    dnf clean all

# system setup for copr-backend
RUN usermod -a -G mock copr

# copy your copr sources to the docker image
COPY . /copr


RUN dnf -y builddep /copr/backend/*.spec --allowerasing && \
    dnf clean all

# build packages from sources
RUN cd /copr/backend && \
    tito build --rpm --test --rpmbuild-options='--nocheck'

# upgrade the already pre-installed packages if possible
RUN dnf -y upgrade /tmp/tito/noarch/copr-backend*.noarch.rpm ; \
    dnf clean all

# copy filesystem setup and setup ownership and permissions
COPY docker/backend/files/ /
RUN chmod 700 /root && \
    chmod 700 /home/copr && \
    chmod 400 /home/copr/.ssh/id_rsa && \
    chmod 600 /home/copr/.ssh/id_rsa.pub && \
    chown -R copr:copr /home/copr

# copr user needs permissions for /bin/sign
RUN gpasswd -a copr obsrun

# copr user needs permissions to create lock files
RUN chmod o+w /var/lock


CMD ["/bin/run.sh"]
