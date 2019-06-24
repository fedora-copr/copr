FROM fedora:30
MAINTAINER copr-devel@lists.fedorahosted.org

ENV container docker
RUN dnf -y update
RUN dnf -y install systemd
RUN (cd /lib/systemd/system/sysinit.target.wants/; for i in *; do [ $i == systemd-tmpfiles-setup.service ] || rm -f $i; done); \
rm -f /lib/systemd/system/multi-user.target.wants/*;\
rm -f /etc/systemd/system/*.wants/*;\
rm -f /lib/systemd/system/local-fs.target.wants/*; \
rm -f /lib/systemd/system/sockets.target.wants/*udev*; \
rm -f /lib/systemd/system/sockets.target.wants/*initctl*; \
rm -f /lib/systemd/system/basic.target.wants/*;\
rm -f /lib/systemd/system/anaconda.target.wants/*;
VOLUME ["/sys/fs/cgroup"]

RUN dnf -y install dnf-plugins-core && dnf -y copr enable @copr/copr
RUN dnf -y install htop wget net-tools iputils vim mlocate git sudo openssh-server psmisc python-jedi procps-ng findutils

# Sanity tests
RUN wget https://beaker-project.org/yum/beaker-client-Fedora.repo -P /etc/yum.repos.d

# Hack, beakerlib is not installable on F30, bug 1719226
RUN sed -i 's/$releasever/29/g' /etc/yum.repos.d/beaker-client-Fedora.repo

RUN dnf -y install rhts-test-env beakerlib

RUN echo "LANG=en_US.UTF-8" >> /etc/locale
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

RUN echo 'root:passwd' | chpasswd
RUN echo 'export LANG=en_US.UTF-8' >> /root/.bashrc

CMD ["/usr/bin/sleep", "infinity"]
