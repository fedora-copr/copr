.. _how_to_upgrade_persistent_instances:
.. _how_to_upgrade_persistent_instances_aws:

How to upgrade persistent instances (Amazon AWS)
================================================

.. note::
   This document is specific to Amazon AWS. For OpenStack, see
   :ref:`this outdated one <how_to_upgrade_persistent_instances_openstack>`.

This article describes how to upgrade persistent instances (e.g. copr-fe-dev) to
a new Fedora version.


Requirements
------------

* access to `Amazon AWS`_
* ssh access to batcave01
* permissions to update aws.fedoraproject.org DNS records


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


2. Choose Instance Type
.......................

You will get redirected to Amazon and asked to choose an instance
type. Currently, we use the following:

+----------------+-------------+-------------+
|                | Dev         | Production  |
+================+=============+=============+
| **frontend**   | t3a.medium  | t3a.xlarge  |
+----------------+-------------+-------------+
| **backend**    | t3a.medium  | c5.4xlarge  |
+----------------+-------------+-------------+
| **keygen**     | t3a.small   | t3a.small   |
+----------------+-------------+-------------+
| **distgit**    | t3a.medium  | t3a.medium  |
+----------------+-------------+-------------+


3. Configure Instance
.....................

- Select ``Network`` without ``| foo`` suffix
- Select ``Subnet`` to be ``us-east-1c``
- Opt-in the ``Protect against accidental termination`` checkbox
- Request IPv6 assignment ``IPv6 IPs -> Add IP``


4. Add Storage
..............

- Update the ``Size (GiB)`` value to resemble root partition size of
  the currently running instance
- Select ``Encryption`` key, don't leave the partition unencrypted


5. Add Tags
...........

- Set ``CoprInstance`` to ``devel`` or ``production``
- Set ``CoprPurpose`` to ``infrastructure``
- Set ``FedoraGroup`` to ``copr``
- Set ``Name`` and add ``-new`` suffix (e.g. ``copr-distgit-dev-new``
  or ``copr-distgit-prod-new``)


6. Configure Security Group
...........................

- Select an existing security group and pick one of
    - ``copr-frontend-sg``
    - ``copr-backend-sg``
    - ``copr-distgit-sg``
    - ``copr-keygen-sg``


7. Review
.........

``Review and Launch`` the instance.


8. Public Key
.............

- Make sure to use existing key pair named ``Ansible Key``.  This allows us to
  run the playbooks on ``batcave01`` box against the newly spawned VM.


9. Pre-prepare the new Backend VM
.................................

It's possible to run the playbook against the new copr-backend server before we
actually shut-down the old one.  But to make sure that ansible won't complain,
there needs to (a) exist a volume attached to the new box with label 'copr-repo'
and we need to have (b) an existing complementary DNS record (copr-be-temp)
poiting to non-elastic IP of the new server.


10. Note the private IP addresses
.................................

Most of the communication within Copr stack happens on public interfaces via hostnames
with one exception. Communication between ``backend`` and ``keygen`` is done on a private
network behind a firewall through IP addresses that change when spawning a fresh instance.

Change its IP address in ``inventory/group_vars/copr_dev``::

    keygen_host: "172.XX.XX.XX"

Whereas after updating a ``copr-backend`` (or dev) instance change the configuration in
``inventory/group_vars/copr_keygen`` (or dev) and update the iptables rules::

    custom_rules: [ ... ]


"Not yet described" section
---------------------------

.. note::
   This document was rewritten during our first upgrade since
   migration to Amazon AWS and we haven't figure out how to do it
   properly. Moreover, we needed to do a couple of one-time things
   (regarding elastic IP addresses), that we probably won't have to do
   the next upgrade. Once things gets clearer, we are going to update
   this section.

.. warning::
   backend - You have to terminate existing resalloc resources.
   See `Terminate resalloc resources`_.

By the end of this section, you should have your DNS records updated
and hostnames pointing to the new unprovisioned instances. By this
point, the outage starts.


Stop the old services
---------------------

Except for the `lighttpd.service` on the old copr-backend (still serving
repositories to users), stop all of our services, timers and cron jobs so they
don't collide or talk with the newly provisioned servers.


Flip the elastic IPs
--------------------

Except for copr-be, flip the Elastic IPs to the new instances.  This is needed
to allow successful run of playbooks.


Don't start the services after first playbook run
-------------------------------------------------

Set the `services_disabled: true` in proper `inventory/group_vars/copr_*`
grop.


Provision new instance from scratch
-----------------------------------

In the fedora-infra ansible repository, edit ``inventory/inventory``
file and set ``birthday=yes`` variable for your host, e.g.::

    [copr_front_dev_aws]
    copr-fe-dev.aws.fedoraproject.org birthday=yes

On batcave01 run playbook to provision the instance.  Note that for backend, you
need to **slightly modify the calls** to use `-l copr-be*-temp...`.

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

The playbook will fail on mounting a data volume (it wasn't attached
to the instance yet). At this point (or if the provisioning got at
least through the ``base`` role), revert the commit to remove the
``birthday`` variable.


Re-Attach the data volume
--------------------------

.. note::
   Frontend - It will most likely be necessary to manualy upgrade the PostgreSQL
   database once you migrated to the new Fedora (new PG major version).
   Don't forget to `Backup the database`_ first.

.. note::
   Distgit - Please be aware that production distgit has 3 volumes in
   total (two of them mounted by label in ansible playbook). This is
   different from all other instances (including ``copr-dist-git-dev``)

.. note::
    Backend - On the new `copr-be*-temp` hostname, stop the lighttpd
    etc. and umount the temporary volume.  It needs to be detached in
    AWS cli, too.

Connect to the old instance via SSH. It doesn't have a hostname
anymore, so you will need to use its public IP address.

Stop all services using the data volume, e.g.::

   systemctl stop lighttpd

.. note::
   Backend - Do not forget to kill all ``/usr/bin/prunerepo`` and
   ``/usr/bin/copr-backend-process-build`` processes. Ideally, you
   should wait until ``/usr/bin/copr-backend-process-action`` gets finished.

.. warning::
    Backend - At this moment you should start **hurry up**, storage is
    down and end-users see failed `dnf update ...` processes in
    terminals.

Umount the data volume and make sure everything is written::

    umount /the/data/directory/mount/point
    sync

Perhaps you can shutdown the instance (but you don't have to)::

    shutdown -h now

And finally open Amazon AWS web UI, select ``Volumes`` in the left
panel, filter them with ``CoprPurpose: infrastructure`` and
``CoprInstance`` either ``devel`` or ``production``. Find the correct
volume, see the instance it is attached to and make sure its stopped.

Then and only then right-click the volume and click to ``Detach
Volume``. Once it is done, right-click the volume again, and click to
``Attach Volume`` (it can be safely attached to a running instance).


Finally flip the BE IP
----------------------

In the AWS attach the copr be elastic IP to the new server.


Fix IPv6 DNS records
--------------------

There is no support for Elastic IPs for IPv6, so we have to update AAAA records
every time we spawn a new infrastructure machine.  SSH to batcave, and setup the
DNS records there according to `the DNS SOP`_.

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

You probably need to `Upgrade the database`_ now on frontend.


"Not yet described" section
---------------------------

Open Amazon AWS web UI, select ``Instances`` in the left panel, and filter
them with ``CoprPurpose: infrastructure``. Rename all instances
without ``-new`` suffix to end with ``-old`` suffix. Then drop
``-new`` suffix from the instances that have it.


Final steps
-----------

Don't forget to announce on `fedora devel`_ and `copr devel`_ mailing lists and also on
``#fedora-buildsys`` that everything should be working again.

Close the infrastructure ticket.

Troubleshooting
---------------

Please note two addresses needs to be updated, both are backend's.

Run provision playbooks for ``copr-backend`` and ``copr-keygen`` to propagate the changes
to the respective instances.

Terminate the old instance
--------------------------

Once you don't need the old VMs, you can terminate them e.g. in Amazon web UI.

.. _`terminate_resalloc_vms`:


Terminate resalloc resources
............................

It is easier to close all resalloc tickets otherwise there will be dangling VMs
preventing the backend from starting new ones.

Edit the ``/etc/resallocserver/pools.yaml`` file and in all section, set::

    max: 0

Then delete all current resources::

    su - resalloc
    resalloc-maint resource-delete $(resalloc-maint resource-list | cut -d' ' -f1)


.. _`terminate_os_vms`:


Backup the database
...................

We periodically create a databse dump and offer users to download
it. At the same time, it can be used as a database backup if something
wrong happens. Please see ``/etc/cron.d/cron-backup-database-coprdb``.
To backup the databse before upgrading it, run::

    [root@copr-fe ~][PROD]# su postgres
    bash-5.0$ /usr/local/bin/backup-database coprdb

Please be aware that the script does ``sleep`` for some
undeterministic amount of time. You might want to kill the ``sleep``
process to speed it up a little.


Upgrade the database
....................

When upgrading to a distribution that provides a new major version of PostgreSQL server,
there is a manual intervention required.

Upgrade the database::

    [root@copr-fe-dev ~][STG]# dnf install postgresql-upgrade
    [root@copr-fe-dev ~][STG]# postgresql-setup --upgrade
    [root@copr-fe-dev ~][STG]# systemctl start postgresql

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
.. _`Amazon AWS`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
.. _`Cloud Base Images`: https://alt.fedoraproject.org/cloud/
.. _`the DNS SOP`: https://fedora-infra-docs.readthedocs.io/en/latest/sysadmin-guide/sops/dns.html
