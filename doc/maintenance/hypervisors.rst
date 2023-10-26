.. _hypervisors:

Fedora Copr hypervisors
=======================

Fedora Copr hosts several hypervisors within the Fedora Infrastructure lab.
These hypervisors are monitored using `Nagios probes`_.

Running playbooks
-----------------

.. warning::
   * ssh access to `batcave01`_ is required

Running playbooks::

    $ ssh batcave01.iad2.fedoraproject.org
    [yourname@batcave01 ~][PROD-IAD2]$ sudo rbac-playbook groups/copr-hypervisor.yml
    ...

Reboot
------

If a hypervisor becomes inconsistent, you may need to reboot it.  The Resalloc
server (starting VMs on the hypervisors) is capable of recovering from the
reboot.

.. warning::
   Please note that any running builds will be rescheduled by **Copr Backend**.

Typically, executing the same hypervisor's playbook with the ``-t
trigger_reboot`` option is sufficient.  However, to avoid rebooting all
hypervisors, you can limit the playbook for specific hosts using the ``-l``
pattern, e.g.::

    one-box $ sudo rbac-playbook groups//copr-hypervisor.yml -t trigger_reboot -l 'vmhost-x86-copr02.rdu-cc.fedoraproject.org'
    all-x86 $ sudo rbac-playbook groups//copr-hypervisor.yml -t trigger_reboot -l '*x86*'
    ...

Access to KVM and cold rebooting
--------------------------------

.. warning::
   * ssh access to ``cloud-noc-os01.rdu-cc.fedoraproject.org`` is needed
   * access to the Team's Bitwaarden account is needed

To access the management consoles of our hypervisors (which are only available
within the local management network), you need to use the
``cloud-noc-os01.rdu-cc.fedoraproject.org`` hop-box.  You can either use
``elinks`` over SSH, or set up a SOCKS proxy for local browsing::

    $ ssh -ND 9999 cloud-noc-os01.rdu-cc.fedoraproject.org

Then, configure Firefox settings by searching for ``socks``, opening *Network
Settings*, and selecting *Manual proxy configuration*.  Specify SOCKS **Host:
localhost**, and **Port: 9999**.  Afterward, you can visit the management
console IP within the management network range, such as ``http://172.X.Y.Z``.

The information regarding IPs and passwords for specific hosts can be found in
the team's *Bitwaarden* account.  Refer to the Secret Note ``Fedora Copr
Hypervisors``.

Adding a new hypervisor
-----------------------

For instructions on adding a new hypervisor, please refer to the separate
section on `how to install hypervisors`_ in the Fedora Infra ansible
repository

.. _`Nagios probes`: https://nagios.fedoraproject.org/nagios/cgi-bin//status.cgi?hostgroup=copr_hypervisor&style=detail
.. _`how to install hypervisors`: https://pagure.io/fedora-infra/ansible/blob/main/f/roles/copr/hypervisor/README
.. _`Batcave01`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/infra-git-repo/
