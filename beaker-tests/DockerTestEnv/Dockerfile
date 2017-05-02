FROM fedora:25
MAINTAINER clime@redhat.com

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

RUN dnf -y install htop
RUN dnf -y install tito
RUN dnf -y install wget
RUN dnf -y install net-tools
RUN dnf -y install iputils
RUN dnf -y install vim
RUN dnf -y install mlocate
RUN dnf -y install git
RUN dnf -y install sudo
RUN dnf -y install openssh-server
RUN dnf -y install dnf-plugins-core
RUN dnf -y install psmisc
RUN dnf -y install python-jedi
RUN dnf -y install procps-ng

# Sanity tests
RUN wget https://beaker-project.org/yum/beaker-client-Fedora.repo -P /etc/yum.repos.d
RUN dnf -y install rhts-test-env beakerlib


RUN echo "LANG=en_US.UTF-8" >> /etc/locale
RUN setcap cap_net_raw,cap_net_admin+p /usr/bin/ping

RUN ssh-keygen -f /etc/ssh/ssh_host_rsa_key -N '' -q

RUN echo 'root:passwd' | chpasswd
RUN echo 'export LANG=en_US.UTF-8' >> /root/.bashrc

RUN dnf -y copr enable @copr/copr-dev

CMD ["/usr/sbin/init"]
