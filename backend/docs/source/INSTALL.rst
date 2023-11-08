INSTALL
=======

1. Obtain rpms:

Get rpm either from upstream copr: https://copr.fedorainfracloud.org/coprs/g/copr/copr/ ::

    dnf copr enable @copr/copr
    dnf install -y copr-backend copr-selinux

2. Configure Resalloc server for automatic VM allocation (either on the same
   machine, or other) ::

    dnf install resalloc-server

   Edit ``/etc/resallocserver/*.yaml`` files to configure.

3. Edit ``/etc/copr/copr-be.conf`` to reflect your setup. Look at example ``backend/conf/copr-be.conf.example``.

4. [Optional] Mount /var/lib/copr/results to the dedicated storage. This location is used to store and serve build results.

5. Enable and start backend processes ::

    systemctl enable copr-backend redis lighttpd
    systemctl start copr-backend redis lighttpd


Side notes
----------
It may be useful to look how copr-backend is deployed at fedora@infrastructure using ansible:
http://infrastructure.fedoraproject.org/infra/ansible/playbooks/groups/copr-backend.yml

