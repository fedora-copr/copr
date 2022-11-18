.. _how_to_upgrade_persistent_instances:
.. _how_to_upgrade_persistent_instances_aws:

How to upgrade persistent instances (Amazon AWS)
************************************************

.. note::
   This document is specific to Amazon AWS. For OpenStack, see
   :ref:`this outdated one <how_to_upgrade_persistent_instances_openstack>`.

This article describes how to upgrade persistent instances (e.g. copr-fe-dev) to
a new Fedora version.


Requirements
============

* access to `Amazon AWS`_
* ssh access to batcave01
* permissions to update aws.fedoraproject.org DNS records



Pre-upgrade
===========

The goal is to do as much work pre-upgrade as possible while focusing
only on important things and not creating a work overload with tasks,
that can be done post-upgrade.

Don't do the pre-upgrade too long before the actual upgrade. Ideally a couple of
hours or a day before.


Launch a new instance
---------------------

First, login into `Amazon AWS`_, otherwise the following step will not
work. Once you are logged-in, feel free to close the page.


1. Choose AMI
.............

Navigate to the `Cloud Base Images`_ download page and scroll down to
the section with cloud base images for Amazon public cloud. Use
``Click to launch`` button to launch an instance from the x86_64
AMI. Select the US East (N. Virginia) region.

You will get redirected to the Amazon AWS page.


2. Name and tags
................

- Set ``Name`` and add ``-new`` suffix (e.g. ``copr-distgit-dev-new``
  or ``copr-distgit-prod-new``)
- Set ``CoprInstance`` to ``devel`` or ``production``
- Set ``CoprPurpose`` to ``infrastructure``
- Set ``FedoraGroup`` to ``copr``


3. Application and OS Images (Amazon Machine Image)
...................................................

Skip this section, we already chose the correct AMI from the Fedora
website.


4. Instance type
................

Currently, we use the following instance types:

+----------------+-------------+-------------+
|                | Dev         | Production  |
+================+=============+=============+
| **frontend**   | t3a.medium  | t3a.xlarge  |
+----------------+-------------+-------------+
| **backend**    | t3a.medium  | c5.4xlarge  |
+----------------+-------------+-------------+
| **keygen**     | t3a.small   | t3a.xlarge  |
+----------------+-------------+-------------+
| **distgit**    | t3a.medium  | t3a.medium  |
+----------------+-------------+-------------+

When more power is needed, please use the `ec2instances.info`_ comparator to get
the cheapest available instance type according to our needs.


5. Key pair (login)
...................

- Make sure to use existing key pair named ``Ansible Key``.  This allows us to
  run the playbooks on ``batcave01`` box against the newly spawned VM.


6. Network settings
...................

- Click the ``Edit`` button in the box heading to show more options
- Select VPC ``vpc-0af***********972``
- Select ``Subnet`` to be ``us-east-1c``
- Switch ``Auto-assign IPv6 IP`` to ``Enable``
- Switch to ``Select existing security group`` and pick one of

    - ``copr-frontend-sg``
    - ``copr-backend-sg``
    - ``copr-distgit-sg``
    - ``copr-keygen-sg``


7. Configure storage
....................

- Click the ``Advanced`` button in the box heading to show more options
- Update the ``Size (GiB)`` of the root partition

+----------------+-------------+-------------+
|                | Dev         | Production  |
+================+=============+=============+
| **frontend**   | 50G         | 50G         |
+----------------+-------------+-------------+
| **backend**    | 20G         | 100G        |
+----------------+-------------+-------------+
| **keygen**     | 10G         | 20G         |
+----------------+-------------+-------------+
| **distgit**    | 20G         | 30G         |
+----------------+-------------+-------------+

- Turn on the ``Encrypted`` option
- Select ``KMS key`` to whatever is ``(default)``


8. Advanced details
...................

- ``Termination protection`` - ``Enable``


9. Launch instance
..................

Click ``Launch instance`` in the right panel.


Pre-prepare the new VM
----------------------

.. note::

   Backend - It's possible to run the playbook against the new copr-backend
   server before we actually shut-down the old one.  But to make sure that
   ansible won't complain, we need

   - A volume attached to the new box with label 'copr-repo'. Use already
     existing volume named ``data-copr-be-dev-initial-playbook-run``
   - An existing complementary DNS record (``copr-be-temp`` or
     ``copr-be-dev-temp``). poiting to the non-elastic IP of the new
     server. See the `DNS SOP`_.


Note the private IP addresses
-----------------------------

Most of the communication within Copr stack happens on public interfaces via
hostnames with one exception. Communication between ``backend`` and ``keygen``
is done on a private network behind a firewall through IP addresses that change
when spawning a fresh instance.

.. note::

   Backend - Whereas after updating a ``copr-backend`` (or dev) instance change
   the configuration in ``inventory/group_vars/copr_keygen_aws`` or
   ``inventory/group_vars/copr_keygen_dev_aws`` and update the iptables rules::

        custom_rules: [ ... ]


Don't start the services after first playbook run
-------------------------------------------------

Set the ``services_disabled: true`` for your instance in
``inventory/group_vars/copr_*_dev_aws`` for devel, or
``inventory/group_vars/copr_*_aws`` for production.


Outage window
=============

Once you start this section, try to be time-efficient because the services are
down and unreachable by users.


Stop the old services
---------------------

Except for the ``lighttpd.service`` on the old copr-backend (still serving
repositories to users), and ``postgresql.service`` on the old copr-frontend (we
will need it to backup the database), stop all of our services.

.. warning::
   Backend - You have to terminate existing resalloc resources.
   See :ref:`Terminate resalloc resources <terminate_resalloc_vms>`.

+----------------+-----------------------------------------+
|                | Command                                 |
+================+=========================================+
| **frontend**   | ``systemctl stop httpd``                |
+----------------+-----------------------------------------+
| **backend**    | ``systemctl stop copr-backend.target``  |
+----------------+-----------------------------------------+
| **keygen**     | ``systemctl stop httpd signd``          |
+----------------+-----------------------------------------+
| **distgit**    | ``systemctl stop copr-dist-git httpd``  |
+----------------+-----------------------------------------+

Stop all timers and cron jobs so they don't collide or talk with the newly
provisioned servers::

    systemctl stop crond
    systemctl stop *timer

.. warning::
   Backend - Do not forget to kill all ``/usr/bin/prunerepo`` and
   ``/usr/bin/copr-backend-process-build`` processes. Ideally, you
   should wait until ``/usr/bin/copr-backend-process-action`` gets finished.


Umount data volumes from old instances
--------------------------------------

.. warning::
   Backend - Keep the backend volume mounted to the old instance. We will take
   care of that later

.. note::
   Distgit - Please be aware that production distgit has 3 volumes in
   total (two of them mounted by label in ansible playbook). This is
   different from all other instances (including ``copr-dist-git-dev``)

.. note::
   Frontend - On the new instance, it will be probably necessary to manually
   upgrade the database to a new PostgreSQL version. This is our last chance to
   :ref:`Backup the database <database_backup>` before the upgrade. Do it.

   Once the backup is created, stop the PostgreSQL server::

       systemctl stop postgresql


It might not be clear what data volumes are mounted. You can checkout
``roles/copr/*/tasks/mount_fs.yml`` in the ansible playbooks to see the data
volumes.

Umount data volumes and make sure everything is written::

    umount /the/data/directory/mount/point
    sync

Perhaps you can shutdown the instance (but you don't have to)::

    shutdown -h now


Attach data volumes to the new instances
----------------------------------------

.. warning::
   Backend - Keep the backend volume attached to the old instance. We will take
   care of that later

Open Amazon AWS web UI, select ``Volumes`` in the left panel, filter them with
``CoprPurpose: infrastructure`` and ``CoprInstance`` either ``devel`` or
``production``. Find the correct volume, select it, and ``Detach Volume``.

+----------------+-------------------------+------------------------------+
|                | Dev                     | Production                   |
+================+=========================+==============================+
| **frontend**   | data-copr-fe-dev        | data-copr-frontend-prod      |
+----------------+-------------------------+------------------------------+
| **backend**    | data-copr-be-dev        | data-copr-backend-prod       |
+----------------+-------------------------+------------------------------+
| **keygen**     | data-copr-keygen-dev    | data-copr-keygen-prod        |
+----------------+-------------------------+------------------------------+
| **distgit**    | data-copr-distgit-dev   | | data-copr-distgit-prod     |
|                |                         | | data-copr-distgit-log-prod |
|                |                         | | copr-dist-git-swap         |
+----------------+-------------------------+------------------------------+

Once it is done, right-click the volume again, and click to ``Attach Volume``
(it can be safely attached to a running instance).


Flip the elastic IPs
--------------------

.. warning::
   Backend - Keep the backend elastic IP associated to the old instance. We will
   take care of that later

Except for copr-be, flip the Elastic IPs to the new instances.  This is needed
to allow successful run of playbooks.

Open Amazon AWS, in the left panel under ``Network & Security`` click to
``Elastic IPs``. Filter them by either ``CoprInstance : devel`` or
``CoprInstance : production``. Select the IP for your instance, and click
``Actions``, ``Associate Elastic IP address`` (don't care that it is already
associated to the old instance).

- In the ``Instance`` field, search for your instance with ``-new`` suffix
- Check-in the ``Check Allow this Elastic IP address to be reassociated`` option


Provision new instance from scratch
-----------------------------------

In the fedora-infra ansible repository, edit ``inventory/inventory``
file and set ``birthday=yes`` variable for your host, e.g.::

    [copr_front_dev_aws]
    copr.stg.fedoraproject.org birthday=yes

On batcave01 run playbook to provision the instance (ignore the playbook for
upgrading Copr packages).

.. note::
   Backend - You need to **slightly modify the calls** to use `-l
   copr-be*-temp...`.

    To make the playbook work with the new `copr-be*-temp` DNS record, we have to
    specify the host name on **TWO PLACES** in inventory inside  ansible.git::

	inventory/inventory -- copr_back_aws vs. copr_back_dev_aws groups
	inventory/cloud -- cloud_aws

    If we don't, when the playbook is run, this breaks the nagios monitoring
    miserably.

For the dev instance, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-dev-machines

and for production, see

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-production-machines

It is possible that the playbook fails, it isn't important now. If the
provisioning gets at least thgourh the ``base`` role, revert the commit to
remove the ``birthday`` variable.


Dealing with backend
--------------------

This is a backend-specific section. For other instaces, skip it completely.

.. note::
    Backend - On the new `copr-be*-temp` hostname, stop the lighttpd
    etc. and umount the temporary volume.  It needs to be detached in
    AWS cli, too.

.. warning::
    Backend - You should **hurry up** and go through this section quickly. The
    storage will be down and end-users will see failed `dnf update ...`
    processes in terminals.

.. note::
    Backend - Connect to the old instance via SSH. It doesn't have a hostname
    anymore, so you will need to use its public IP address.

    Stop all services using the data volume, e.g.::

        systemctl stop lighttpd

    Safely ummount the data volume

    See `Umount data volumes from old instances`_

.. note::
   Backend - Open Amazon AWS, detach the data volume from the old backend
   instance, and a attach it to the new one.

   See `Attach data volumes to the new instances`_

.. note::
   Backend - Open Amazon AWS and finally flip the backend elastic IP address
   from the old instance to the new one.

   See `Flip the elastic IPs`_

.. note::
   Backend - Re-run the playbook again, this time with the correct hostname
   (without ``-temp``) and drop the ``birthday=yes`` parameter.


Get it working
--------------

Re-run the playbook from previous section again, with dropped configuration::

    services_disabled: false

It's encouraged to start with backend so the repositories are UP again.  Since
we have fully working DNS and elastic IPs, even copr-backend playbook can be run
with normal `-l` argument.

It should get past mounting but it will most likely **not** succeed. At this
point, you need to debug and fix the issues from running it. If required, adjust
the playbook and re-run it again and again (pay attention to start lighttpd
serving the repositories ASAP).

.. note::
   Frontend - It will most likely be necessary to manualy upgrade the PostgreSQL
   database once you migrated to the new Fedora (new PG major version).
   See how to :ref:`Upgrade the database <postgresql_upgrade>`.


.. note::
   Keygen - If you upgraded keygen before backend, you need to re-run keygen
   playbook once more to allow the new backend private IP address in the
   iptables.


Update IPv6 addresses
---------------------

Update the ``aws_ipv6_addr`` for your instance in
``inventory/group_vars/copr_*_dev_aws`` for devel, or
``inventory/group_vars/copr_*_aws`` for production.

Then run the playbooks once more with ``-t ipv6_config`` and reboot the
instance (or figure out a better way to get them working).


Fix IPv6 DNS records
--------------------

There is no support for Elastic IPs for IPv6, so we have to update AAAA records
every time we spawn a new infrastructure machine.  SSH to batcave, and setup the
DNS records there according to the `DNS SOP`_.


Post-upgrade
============

At this moment, every Copr service should be up and running.


Drop suffix from instances names
--------------------------------

Open Amazon AWS web UI, select ``Instances`` in the left panel, and filter
them with ``CoprPurpose: infrastructure``. Rename all instances
without ``-new`` suffix to end with ``-old`` suffix. Then drop
``-new`` suffix from the instances that have it.


.. _`terminate_os_vms`:

Terminate the old instances
---------------------------

Once you don't need the old VMs, you can terminate them e.g. in Amazon web
UI. You can do it right after the upgrade or wait a couple of days to be sure.

The instances should be protected against accidental termination, and therefore
you need to click ``Actions``, go to ``Instance settings``,
``Change termination protection``, and disable this option.


Final steps
-----------

Don't forget to announce on `fedora devel`_ and `copr devel`_ mailing lists and also on
``#fedora-buildsys`` that everything should be working again.

Close the infrastructure ticket, the upgrade is done.



.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
.. _`Fedora infrastructure issue #7966`: https://pagure.io/fedora-infrastructure/issue/7966
.. _`fedora devel`: https://lists.fedorahosted.org/archives/list/devel@lists.fedoraproject.org/
.. _`copr devel`: https://lists.fedoraproject.org/archives/list/copr-devel@lists.fedorahosted.org/
.. _`Amazon AWS`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
.. _`Cloud Base Images`: https://alt.fedoraproject.org/cloud/
.. _`DNS SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/dns/
.. _`ec2instances.info`: https://ec2instances.info/
