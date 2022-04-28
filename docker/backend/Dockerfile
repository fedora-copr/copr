FROM registry.fedoraproject.org/fedora:35
MAINTAINER copr-devel@lists.fedorahosted.org

ENV export LANG=en_US.UTF-8
ENV PYTHONPATH="/usr/share/copr/"

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
                   resalloc \
                   psmisc \
                   nginx \
                   python3-ipdb \
                   findutils \
# to get more entropy for generation of gpg keys
                   rng-tools \
# for unbuffer package
                   expect \
    && dnf clean all

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

# Install copr-backend package
RUN dnf -y install copr-backend && \
    dnf clean all

# system setup for copr-backend
RUN usermod -a -G mock copr

# copy filesystem setup and setup ownership and permissions
COPY files/ /
RUN chmod 700 /root && \
    chmod 700 /home/copr && \
    chmod 400 /home/copr/.ssh/id_rsa && \
    chmod 600 /home/copr/.ssh/id_rsa.pub && \
    chown -R copr:copr /home/copr

# copr user needs permissions for /bin/sign
RUN gpasswd -a copr obsrun

# Not sure why the directory wasn't created automatically
RUN mkdir /var/lock/copr-backend
RUN chown copr:copr /var/lock/copr-backend

# using /dev/urandom is a hack just for devel, /dev/hwrandom or /dev/hwrng should be used in production
RUN rngd -r /dev/urandom

CMD ["/bin/run.sh"]
