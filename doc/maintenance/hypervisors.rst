.. _hypervisors:

Fedora Copr hypervisors
=======================

Fedora Copr hosts several hypervisors within the RDU3 Fedora Infrastructure lab.
These hypervisors are monitored using `Nagios probes`_.

Running playbooks
-----------------

.. warning::
   * ssh access to `batcave01`_ is required

Running playbooks::

    $ ssh batcave01.rdu3.fedoraproject.org
    [yourname@batcave01 dns][PROD-RDU3]$ sudo rbac-playbook groups/copr-hypervisor.yml
    ...

Reboot
------

If a hypervisor becomes inconsistent, a reboot may be necessary.  Both the Copr
Backend and the Resalloc server (which handles VM provisioning on the
hypervisors) are capable of recovering from a reboot; any builds on the affected
VMs will, of course, be automatically restarted.

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
   * ssh access to ``bastion.fedoraproject.org`` is needed
   * access to the Team's Bitwarden account is needed

See how to `restart server in Fedora DC`_ first.  That might give you a good
(and up2date) idea.

To access the management consoles of our hypervisors (which are only available
within the local management network), you need to use the

``bastion.fedoraproject.org`` hop-box.  You can either use
``elinks`` over SSH, or set up a SOCKS proxy for local browsing::

    $ ssh -ND 9999 bastion.fedoraproject.org

Then, configure Firefox settings by searching for ``socks``, opening *Network
Settings*, and selecting *Manual proxy configuration*.  Specify SOCKS **Host:
localhost**, and **Port: 9999**.  Afterward, you can visit the management
console IP within the management network range, such as ``https://10.16.X.X``.

Alternatively go through ``chromium-browser --proxy-server="socks5://localhost:9999"``.

The information regarding passwords for specific hosts can be found in the
team's Bitwarden account.  Refer to the Bitwarden Secret Note ``Fedora Copr
Hypervisors``.  The specific IP address can be found by pinging the mgmt host
from batcave, e.g.::

    [yourname@batcave01 dns][PROD-RDU3]$ ping vmhost-p09-copr02.mgmt.rdu3.fedoraproject.org
    PING vmhost-p09-copr02.mgmt.rdu3.fedoraproject.org (10.16.X.Y) 56(84) bytes of data.

Adding a new hypervisor
-----------------------

For instructions on adding a new hypervisor, please refer to the separate
section on `how to install hypervisors`_ in the Fedora Infra ansible
repository

.. _`Nagios probes`: https://nagios.fedoraproject.org/nagios/cgi-bin//status.cgi?hostgroup=copr_hypervisor&style=detail
.. _`how to install hypervisors`: https://pagure.io/fedora-infra/ansible/blob/main/f/roles/copr/hypervisor/README
.. _`Batcave01`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/infra-git-repo/
.. _`restart server in Fedora DC`: https://docs.fedoraproject.org/en-US/infra/howtos/restart_datacenter_server/
