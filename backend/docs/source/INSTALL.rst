INSTALL
=======

1. Obtain rpms:

Get rpm either from upstream copr: https://copr.fedorainfracloud.org/coprs/g/copr/copr/ ::

    dnf copr enable @copr/copr
    dnf install -y copr-backend copr-selinux

or checkout git repo and build with rpkg::

    git clone https://pagure.io/copr/copr.git
    dnf install -y rpkg
    dnf builddep backend/copr-backend.spec
    dnf builddep selinux/copr-selinux.spec
    dnf builddep python/python-copr.spec
    cd backend && rpkg local && cd ..
    cd selinux && rpkg local && cd ..
    cd python && rpkg local && cd ..
    dnf install -C <path to the built rpms>


2. Prepare ansible playbooks to spawn and terminate VM builders using your VM provider.
    You could find some inspiration in ``backend/conf/playbooks/``.

3. Edit ``/etc/copr/copr-be.conf`` to reflect your setup. Look at example ``backend/conf/copr-be.conf.example``.

4. [Optional] Mount /var/lib/copr/results to the dedicated storage. This location is used to store and serve build results.

5. Enable and start backend processes ::

    systemctl enable copr-backend redis lighttpd
    systemctl start copr-backend redis lighttpd


Side notes
----------
It may be useful to look how copr-backend is deployed at fedora@infrastructure using ansible:
http://infrastructure.fedoraproject.org/infra/ansible/playbooks/groups/copr-backend.yml

