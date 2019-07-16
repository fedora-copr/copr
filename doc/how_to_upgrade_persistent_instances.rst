.. _how_to_upgrade_persistent_instances:

How to upgrade persistent instances
===================================

This article describes how to upgrade persistent instances (e.g. copr-fe-dev) to new Fedora version.


Requirements
------------

* an account on `Fedora Infra OpenStack`_
* access to persistent tenant
* ssh access to batcave01


Find source image
-----------------

For OpenStack, there is an image registry on `OpenStack images dashboard`_.  By
default you see only the project images; to see all of them, click on the
``Public`` button.

Search for the ``Fedora-Cloud-Base-*`` images of the particular Fedora. Please note
that if there is a timestamp in the image name suffix than it is a beta version.
It is better to use images with numbered minor version.

The goal in this step is just to find an image name.


Update the image in playbooks
-----------------------------

Once the new image name is known, make sure it is set in `vars/global.yml`, e.g.::

    fedora30_x86_64: Fedora-Cloud-Base-30-1.2.x86_64

Then edit the host vars for the instance::

    vim inventory/host_vars/<instance>.fedorainfracloud.org
    # e.g.
    vim inventory/host_vars/copr-dist-git-dev.fedorainfracloud.org

And configure it to use the new image::

    image: "{{ fedora30_x86_64 }}"

That is all, that needs to be changed in the ansible repository. Commit and push it.


Backup the old instance
-----------------------

This part is done via ``openstack`` client on your computer. First, download a RC
file for the ``persistent`` tenant. Open `Fedora Infra OpenStack`_ dashboard, switch
to the ``Access & Security`` section, then ``API Access`` and click on
``Download OpenStack RC File``.

Load the openstack settings::

    source ~/Downloads/persistent-openrc.sh

Detach volume from the old instance::

    openstack server remove volume "<instance_id>" "<volume_id>"
    # e.g.
    openstack server remove volume "52d97d72-5915-45c0-b223-xxxxxxxxxxxx" "9e2b4c55-9ec3-4508-af46-xxxxxxxxxxxx"

Backup the old instance by renaming it::

    openstack server set --name <old_name>_backup "<id>"
    # e.g.
    openstack server set --name copr-dist-git-dev_backup "85260b5b-7f61-4398-8d05-xxxxxxxxxxxx"


.. note:: You might need to backup also letsencrypt certificates.
          See `Letsencrypt renewal limits`_.

.. note:: You should terminate existing resalloc resources.
          See `Terminate resalloc resources`_.


Finally, shutdown the instance to avoid storage inconsistency and other possible problems::

    $ ssh root@<old_name>.fedorainfracloud.org
    [root@copr-dist-git-dev ~][STG]# shutdown -h now


Provision new instance from scratch
-----------------------------------

On batcave01 run playbook to provision the instance. For dev, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-dev-machines

and for production, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-production-machines

.. note:: Please note that the playbook may stuck longer than expected while waiting for a new
          instance to boot. See `Initial boot hangs waiting for entropy`_.


Terminate the old instance
--------------------------

Once the new instance is successfully provisioned and working as expected, terminate the
old backup instance.

Open the `OpenStack instances dashboard`_ and switch the current project to ``persistent``
and find the instance, that you want to terminate. Make sure, it is the right one! Don't
mistake e.g. production instance with dev. Then look at the ``Actions`` column and click
``More`` button. In the dropdown menu, there is a button ``Terminate instance``, use it.


Troubleshooting
---------------

Initial boot hangs waiting for entropy
......................................

Because of a known infrastructure issue `Fedora infrastructure issue #7966`_ initial boot
of an instance in OpenStack hangs and waits for entropy. It seems that it can't be fixed
properly, so we need to workaround by going to `OpenStack instances dashboard`_, opening
the instance details, switching to the ``Console`` tab and typing random characters in it.
It resumes the booting process.


Letsencrypt renewal limits
..........................

Currently we renew our letsencrypt certificates on daily basis through ``certbot-renew.timer``
service. However, letsencrypt website provides at maximum five certificates a week (think of
a week as a 7 day floating window, instead of a calendar week) per a domain. As a consequence
it may happen, that our new instance won't be able to obtain a certificate for two days,
with no way to bypass it. Don't let this happen on production instances!

There are two possible options how to deal with this situation at the moment. Either disable
``certbot-renew.timer`` at least two days ahead of upgrading an instance or backup its
current certificates and copy them to the upgraded instance::

    [root@copr-be-dev ~][STG]# tar zcvf /tmp/copr-be-dev-letsencrypt.tar.gz /etc/letsencrypt
    $ scp root@copr-be-dev.cloud.fedoraproject.org:/tmp/copr-be-dev-letsencrypt.tar.gz /tmp/

Once a new instance is provisioned and unable to obtain certificates from the letsencrypt
site, copy them from backup::

    $ scp /tmp/copr-be-dev-letsencrypt.tar.gz root@copr-be-dev.cloud.fedoraproject.org:/tmp
    [root@copr-be-dev ~][STG]# tar zxvf /tmp/copr-be-dev-letsencrypt.tar.gz -C /

Remove the backup from your computer, it contains secret files::

    $ rm /tmp/copr-be-dev-letsencrypt.tar.gz


Private IP addresses
....................

The most of the communication within Copr stack happens on public interfaces via hostnames
with one exception. Communication between ``backend`` and ``keygen`` is done on private
network behind firewall through IP addresses that change when spawning a fresh instance.

After updating a ``copr-keygen`` (or dev) instance, change its IP address in
``inventory/group_vars/copr_dev``::

    keygen_host: "172.XX.XX.XX"

Whereas after updating a ``copr-backend`` (or dev) instance change the configuration in
``inventory/group_vars/copr_keygen`` (or dev) and update the iptable rules::

    custom_rules: [ ... ]

Please note there are two addresses that needs to be updated, both are backend's.


Terminate resalloc resources
............................

It is easier to close all resalloc tickets otherwise there will be dangling VMs
preventing the backend from starting new ones.

Edit the ``/etc/resallocserver/pools.yaml`` file and in all section, set::

    max: 0

Then delete all current resources::

    su - resalloc
    resalloc-maint resource-delete $(resalloc-maint resource-list | cut -d' ' -f1)





.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
.. _`Fedora infrastructure issue #7966`: https://pagure.io/fedora-infrastructure/issue/7966
