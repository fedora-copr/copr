INSTALL
=======

1. Obtain rpms:

Get rpm either from upstream copr: https://copr.fedoraproject.org/coprs/msuchy/copr/ ::

    dnf copr enable msuchy/copr
    dnf install -y copr-backend copr-selinux



or checkout git repo and build latest release with tito::

    git clone https://git.fedorahosted.org/cgit/copr.git
    yum install -y tito yum-utils
    yum-builddep backend/copr-backend.spec
    yum-builddep selinux/copr-selinux.spec
    yum-builddep python/python-copr.spec
    cd backend && tito build --rpm && cd ..
    cd selinux && tito build --rpm && cd ..
    cd python && tito build --rpm && cd ..
    yum localinstall <path to the built rpms>


2. Prepare ansible playbooks to spawn and terminate VM builders using your VM provider.
    You could find some inspiration in ``backend/conf/playbooks/``.

3. Edit ``/etc/copr/copr-be.conf`` to reflect your setup. Look at example ``backend/conf/copr-be.conf.example``.

4. [Optional] Mount /var/lib/copr/results to the dedicated storage. This location is used to store and serve build results.

5. Enable and start backend processes ::

    systemctl enable copr-backend redis lighttpd
    systemctl start copr-backend redis lighttpd


Side notes
----------
It maybe usefull to look how copr-backend is deployed at fedora@infrastructure using ansible:
http://infrastructure.fedoraproject.org/infra/ansible/playbooks/groups/copr-backend.yml

