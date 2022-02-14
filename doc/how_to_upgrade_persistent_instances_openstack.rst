.. _how_to_upgrade_persistent_instances_openstack:

How to upgrade persistent instances (OpenStack)
===============================================

.. warning::
   This document is specific to OpenStack and is outdated. For Amazon
   AWS, see :ref:`this up-to-date one <how_to_upgrade_persistent_instances_aws>`.

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

This part is done via ``openstack`` client on your computer. First, download an RC
file for the ``persistent`` tenant. Open `Fedora Infra OpenStack`_ dashboard, switch
to the ``Access & Security`` section, then ``API Access`` and click on
``Download OpenStack RC File``.

Load the openstack settings::

    source ~/Downloads/persistent-openrc.sh

Backup the old instance by renaming it::

    openstack server set --name <old_name>_backup "<id>"
    # e.g.
    openstack server set --name copr-dist-git-dev_backup "85260b5b-7f61-4398-8d05-xxxxxxxxxxxx"


.. warning:: backend - You have to terminate existing resalloc resources.
             See `Terminate resalloc resources`_.

.. warning:: backend - `Terminate OpenStack VMs`_.

Finally, shut down the instance to avoid storage inconsistency and other possible problems::

    $ ssh root@<old_name>.fedorainfracloud.org
    [root@copr-dist-git-dev ~][STG]# shutdown -h now

Once the instance is halted, detach volume from the old instance::

    openstack server remove volume "<instance_id>" "<volume_id>"
    # e.g.
    openstack server remove volume "52d97d72-5915-45c0-b223-xxxxxxxxxxxx" "9e2b4c55-9ec3-4508-af46-xxxxxxxxxxxx"


Provision new instance from scratch
-----------------------------------

On batcave01 run playbook to provision the instance. For dev, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-dev-machines

and for production, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-production-machines

.. note:: Please note that the playbook may be stuck longer than expected while waiting for a new
          instance to boot. See `Initial boot hangs waiting for entropy`_.


Get it working
--------------

The playbook from the previous section will most likely **not** succeed. At this point,
you need to debug and fix the issues from running it. If required, adjust the playbook
and re-run it again and again. Most likely you will also need to attach a volume to it
in the `OpenStack instances dashboard`_.

.. note:: frontend - It will most likely be necessary to manualy upgrade the database.
          See `Upgrade the database`_.

.. note:: backend - Copr backend requires an outdated version of python3-novaclient.
          See `Downgrade python novaclient`_.


Terminate the old instance
--------------------------

Once the new instance is successfully provisioned and working as expected, terminate the
old backup instance.

Open the `OpenStack instances dashboard`_ and switch the current project to ``persistent``
and find the instance, that you want to terminate. Make sure, it is the right one! Don't
mistake e.g. production instance with dev. Then look at the ``Actions`` column and click
``More`` button. In the dropdown menu, there is a button ``Terminate instance``, use it.


Final steps
-----------

Don't forget to announce on `fedora devel`_ and `copr devel`_ mailing lists and also on
``#fedora-buildsys`` that everything should be working again.

Close the infrastructure ticket.


Troubleshooting
---------------

Initial boot hangs waiting for entropy
......................................

Because of a known infrastructure issue `Fedora infrastructure issue #7966`_ initial boot
of an instance in OpenStack hangs and waits for entropy. It seems that it can't be fixed
properly, so we need to work around by going to `OpenStack instances dashboard`_, opening
the instance details, switching to the ``Console`` tab and typing random characters in it.
It resumes the booting process.


Private IP addresses
....................

Most of the communication within Copr stack happens on public interfaces via hostnames
with one exception. Communication between ``backend`` and ``keygen`` is done on a private
network behind a firewall through IP addresses that change when spawning a fresh instance.

After updating a ``copr-keygen`` (or dev) instance, change its IP address in
``inventory/group_vars/copr_dev``::

    keygen_host: "172.XX.XX.XX"

Whereas after updating a ``copr-backend`` (or dev) instance change the configuration in
``inventory/group_vars/copr_keygen`` (or dev) and update the iptables rules::

    custom_rules: [ ... ]

Please note two addresses needs to be updated, both are backend's.

Run provision playbooks for ``copr-backend`` and ``copr-keygen`` to propagate the changes
to the respective instances.


Terminate resalloc resources
............................

It is easier to close all resalloc tickets otherwise there will be dangling VMs
preventing the backend from starting new ones.

Edit the ``/etc/resallocserver/pools.yaml`` file and in all section, set::

    max: 0

Then delete all current resources::

    su - resalloc
    resalloc-maint resource-delete --all


Terminate OpenStack VMs
.......................

Make sure you terminate all the OpenStack located builders allocated by
``copr-backend.service``::

    # systemctl stop copr-backend # ensure that new are not allocated anymore
    # su - copr

    # drop the builders from DB
    $ redis-cli --scan --pattern 'copr:backend:vm_instance:hset::Copr_builder_*' | xargs redis-cli del

    # shutdown all the VMs which are not in DB
    $ cleanup_vm_nova.py


Downgrade python novaclient
...........................

Backend is dependent on ``python3-novaclient`` in prehistoric version ``3.3.1``. This
version is no longer supported and the spec file needed to be customized to build and
install only python3 package. Also, the epoch has been bumped so it doesn't get replaced
with a newer version. Please install this package from Copr project (even on production
instance)::

    dnf copr enable @copr/novaclient
    dnf install python3-novaclient-2:3.3.1

.. note:: Please do not automatize this step in the playbook, so it forces us to deal
          with the situation properly.


Upgrade the database
....................

When upgrading to a distribution that provides a new major version of PostgreSQL server,
there is a manual intervention required.

Upgrade the database::

    [root@copr-fe-dev ~][STG]# dnf install postgresql-upgrade
    [root@copr-fe-dev ~][STG]# postgresql-setup --upgrade


And rebuild indexes::

    [root@copr-fe-dev ~][STG]# su postgres
    bash-5.0$ cd
    bash-5.0$ reindexdb --all



.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
.. _`Fedora infrastructure issue #7966`: https://pagure.io/fedora-infrastructure/issue/7966
.. _`fedora devel`: https://lists.fedorahosted.org/archives/list/devel@lists.fedoraproject.org/
.. _`copr devel`: https://lists.fedoraproject.org/archives/list/copr-devel@lists.fedorahosted.org/
