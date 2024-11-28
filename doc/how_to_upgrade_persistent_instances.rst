.. _how_to_upgrade_persistent_instances:
.. _how_to_upgrade_persistent_instances_aws:

How to Upgrade Fedora Copr Persistent VMs (Amazon AWS)
******************************************************

This document describes the process of upgrading persistent VM instance(s)
(e.g., ``copr-fe-dev.aws.fedoraproject.org``) to a new Fedora version by
creating a completely new VM to replace the old one.

Requirements
============

* Access to the team's `Amazon AWS account`_ and proper configuration of that account according to the `README.md <helper playbook repository_>`_.
* Permissions to run playbooks on `batcave01 <playbook SOP_>`_.
* Since we do not modify the public IPs (neither v4 nor v6), no DNS
  modifications should be required.  However, familiarize yourself with the `DNS
  SOP`_ in case of any issues.
* Make sure you have `/usr/bin/aws` installed and that you have `fedora-copr`
  section in  `~/.aws/credentials`

Pre-upgrade
===========

The goal is to complete as much pre-upgrade work as possible while focusing on
minimizing the **outage window** and only performing essential tasks that cannot
be done post-upgrade.

Avoid conducting the pre-upgrade too far in advance of the actual upgrade.
Ideally, perform this phase a couple of hours or a day before.

Announce the outage
-------------------

See a specific document :ref:`announcing_fedora_copr_outage`, namely the
"planned" outage state.

Check the hot-fixes
-------------------

The old set of instances (especially prod) has been running for quite some time,
likely accumulating several hotfixes over that period.  Research the applied
hotfixes and determine which of them need to be manually implemented on the N+2
boxes (if any, note them).

First, check the `hot-fixed issues and PRs <https://github.com/fedora-copr/copr/issues?q=label%3Ahot-fixed+is%3Aclosed>`_.
Then, check the file-system modifications::

    # over ssh on the _old_ box, search for weird things (ignore config changes
    # and /boot)
    [root@copr-be-dev ~][STG]# rpm -Va | grep -v -e /etc/ -e /boot/
    ...
    S.5....T.    /var/www/cgi-resalloc
    ...
    S.5....T.    /usr/lib/python3.12/site-packages/copr_backend/pulp.py
    ...

E.g., the ``/var/www/cgi-resalloc`` file is a weird change, but that in
particular is covered `in playbooks <https://pagure.io/fedora-infra/ansible/c/d6ede12e3247f7b5f5d8b4dafc1710ae6987847c>`_.
The ``pulp.py`` change is important to note though!  You may consult the
``dnf diff copr-backend`` output, find the corresponding upstream PR on GitHub,
and tag the PR with ``hot-fixed`` label (if not already done).


Preparation
-----------

Ensure you have the `helper playbook repository`_ cloned locally and navigate to
the clone directory.

Review the ``dev.yml``, ``prod.yml``, and ``all.yml`` configurations in the
``./group_vars`` directory.  Pay particular attention to the data volume IDs as
**these MUST match the EC2 reality**.

In the following moments, you will run several playbooks on your machine.
During execution, explicitly specify two Ansible variables, ``copr_instance``
(set to either ``dev`` or ``prod``) and ``server_id`` (set to either
``frontend``, ``backend``, ``distgit``, or ``keygen``).  For example::

    $ opts=( -e copr_instance=dev -e server_id=keygen )
    $ ansible-playbook play-vm-migration-01-new-box.yml "${opts[@]}"

Identify the AMI (golden images) you want to use for the new VM instances.
Typically, upgrade to ``Fedora N+2`` (e.g., migrating infrastructure from Fedora
37 to Fedora 39).  Visit the `Cloud Base Images`_ download page, locate the
**Launch on public cloud platforms** section for **x86_64-based instances**, and
click the button next to **Fedora Cloud 41 AWS** (ensure JavaScript is enabled
for this page!).  Note the ``ami-*`` ID in the **US East (N. Virginia)** region
(for example ``ami-0746fc234df9c1ee0``).  Specify this ``ami-*`` ID in
``group_vars/all.yml``, and ensure both ``group_vars/{dev,prod}.yml`` correctly
reference it.

Double-check other machine parameters such as instance types, names, tags, IP
addresses, root volume sizes, etc.  Usually, the pre-filled defaults suffice,
but verification is recommended.

.. note::
   Use the `ec2instances.info`_ comparator to find the cheapest available
   instance type that meets our needs whenever more power is required.

.. note::

   Don't worry about ``old_instance_id`` and ``new_instance_id`` for now. We
   will change them after running the first set of playbooks

.. warning::

   The ``group_vars/`` directory serves as the primary source of truth for the
   Fedora Copr instances.  Update the configuration in this directory whenever
   you ad-hoc modify some EC2 instance parameters in the future!

Key pair named ``Ansible Key`` must be used.  This allows us
to initially run the playbooks from ``batcave01`` box against the newly
spawned VM.  The playbooks assure that, subsequently, Fedora Copr team members
can SSH using their own keys, uploaded to FAS.

Backup the Current Let's Encrypt Certificates
---------------------------------------------

We will copy and paste the certificate files used on the old set of VMs onto the
new VMs.  These certificates will remain in use until automatically renewed by
the certbot daemon.  The process begins by copying the certificate files to the
``batcave01`` through the execution of playbooks with the ``-t certbot`` option.
For instance::

    $ sudo rbac-playbook -l copr-keygen.aws.fedoraproject.org groups/copr-keygen.yml -t certbot

Do this for all the instances!

Launch new instances
--------------------

As simple as::

    $ opts=( -e copr_instance=dev -e server_id=keygen )
    $ ansible-playbook play-vm-migration-01-new-box.yml "${opts[@]}"

You'll see an output like::

    ok: [localhost] => {
        "msg": [
            "ElasticIP: not specified",
            "Instance ID: i-04ba36eb360187572",
            "Network ID: eni-048189f432f068270",
            "Unused Public IP: 100.24.62.79",
            "Private IP: 172.30.2.94"
        ]
    }

Now fix the corresponding ``new_instance_id`` and ``new_network_id`` options in
``group_vars/{dev,prod}.yml`` according to the output. Also update
``old_instance_id`` and ``old_network_id`` options.

Note the Private IP addresses
-----------------------------

Most of the communication within Copr stack happens on public interfaces via
hostnames with one exception.  Communication between ``backend`` and ``keygen``
is done on a private network behind a firewall through IP addresses that change
when spawning a fresh instances.

So once you know the Backend's private IP, please do a `private IP change`_ in
ansible.git.

Don't start the services after the first playbook run
-----------------------------------------------------

Set the ``services_disabled: true`` for your instance in
``inventory/group_vars/copr_*_dev_aws`` for devel, or
``inventory/group_vars/copr_*_aws`` for production.

Pre-prepare the new VM — backend only!
--------------------------------------

.. note::

   Running the playbook against the new copr-backend server before shutting down
   the old one is possible.  This minimizes the outage duration with non-working
   DNF repositories on the backend, which is highly desirable.

   However, to prevent any issues with Ansible, the following prerequisites are
   necessary:

   - A temporary volume attached to the new box that provides an ext4 filesystem
     with the ``copr-repo`` label.

   - An existing temporary hostname (having an existing DNS record) to execute
     the playbook against it.

   The volume, DNS record, and corresponding Elastic IP for this purpose have
   already been prepared by the ``play-vm-migration-01-new-box.yml`` playbook
   mentioned above.

.. note::

    The following inventory configuration should already be prepared for you in
    the "commented-out" form.

Ensure that the ``copr-be-dev-temp.aws.fedoraproject.org`` is specified in the
inventory in the following groups::

    copr_back_dev_aws
    staging
    cloud_aws

Similarly, use ``copr-be-temp.aws.fedoraproject.org`` in::

    copr_back_aws
    cloud_aws

For both cases, set the ``birthday=yes`` variable for the temporary hostname::

    [copr_back_dev_aws]
    copr-be-dev.aws.fedoraproject.org
    copr-be-dev-temp.aws.fedoraproject.org birthday=yes

On Batcave, execute the playbook against the temporary hostname::

    $ sudo rbac-playbook -l copr-be-dev-temp.aws.fedoraproject.org groups/copr-backend.yml
    $ sudo rbac-playbook -l copr-be-temp.aws.fedoraproject.org     groups/copr-backend.yml

Once the playbook finishes successfully, remember to revert the inventory
changes we did here (commenting out again).

Outage window
=============

When initiating this section, aim for time efficiency as the services will be
down and inaccessible to users.

Let users know
--------------

See :ref:`announcing_fedora_copr_outage` again, ad "ongoning" issue.

Move IPs and Volumes to the New Instances
-----------------------------------------

.. warning::
   Prepare to follow the instructions provided during the playbook run.  You'll
   need to perform manual steps such as DB backups, consistency checks, etc.

Migrate the data volumes and IP addresses to the new machine.  For the Backend
case, a separate playbook is created.  This playbook makes the
`results directory <https://copr-be.cloud.fedoraproject.org/results/>`_
unavailable temporarily, affecting every Copr consumer!  Ensure that that the
``lighttpd`` service is running on the new server once the playbook finishes,
and that it hosts the correct results::

    $ ansible-playbook play-vm-migration-02-migrate-backend-box.yml "${opts[@]}"

For the rest of the systems (Frontend, DistGit, Keygen), use::

    $ ansible-playbook play-vm-migration-02-migrate-non-backend-box.yml "${opts[@]}"

Provision the new instances
---------------------------

In the fedora-infra ansible repository, edit the ``inventory/inventory`` file
and set the ``birthday=yes`` variable for your updated host, for example::

    [copr_front_dev_aws]
    copr.stg.fedoraproject.org birthday=yes

This is necessary to instruct the first playbook run on ``batcave01`` to sign
the new host certificates (avoiding later manipulation with ``known_hosts``).

On ``batcave01``, execute the playbook to provision the instance (ignore the
playbook for upgrading Copr packages).  For the dev instance, refer to

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-dev-machines

and for production, refer to

https://docs.pagure.org/copr.copr/how_to_release_copr.html#upgrade-production-machines

It's possible that the playbook fails, but it typically isn't crucial now.  If
provisioning at least reaches the end of the ``base`` role, revert the
``birthday=yes`` commit and proceed with the next steps.

The playbooks above have not automatically updated the systems.  If you prefer
to start on Fedora N+2 with up-2-date set of packages, do the ``dnf update`` now
(manual step over ssh).

Get it working
--------------

Rerun the playbook from the previous section again, with dropped configuration::

    services_disabled: false

It should proceed with mounting data volumes but will likely not succeed.  Now,
you'll need to debug and address the issues.  If necessary, modify and rerun the
playbook multiple times (ensuring ``lighttpd`` running on the new backend all
the time).

.. note::
   Frontend - You'll likely need to manually upgrade the PostgreSQL database
   once you migrate to the new Fedora (new PG major version).  Refer to
   :ref:`Upgrade the database <postgresql_upgrade>`.

Post-upgrade
============

By this point, every Copr service should be operational.

It's a good idea to test ``/usr/sbin/reboot`` now to debug potential boot issues
during the outage window, as future reboots are likely to occur at the most
inconvenient times.

Rename the instance names
-------------------------

Remove the ``-new`` name suffix from the new instances and add a ``-old`` suffix
to the old instances.  This playbook should be executed only once for all the
infra instances::

    $ opts=( -e copr_instance=dev )  # or prod
    $ ansible-playbook play-vm-migration-03-rename-instances.yml "${opts[@]}"

Terminate the old instances
---------------------------

Once you no longer require the old VMs, you can terminate them using the Amazon
web UI.  You can do this immediately after the upgrade or wait a couple of days
(e.g. to keep the DB ``/backups`` for a while just in case of any problems).

The old VMs are protected against accidental termination.  To disable this
option, click ``Actions``, navigate to ``Instance settings`` and then to
``Change termination protection``.

Final steps
-----------

See a specific document :ref:`announcing_fedora_copr_outage`, the "resolved"
section.

.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
.. _`Fedora infrastructure issue #7966`: https://pagure.io/fedora-infrastructure/issue/7966
.. _`fedora devel`: https://lists.fedorahosted.org/archives/list/devel@lists.fedoraproject.org/
.. _`copr devel`: https://lists.fedoraproject.org/archives/list/copr-devel@lists.fedorahosted.org/
.. _`Amazon AWS account`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
.. _`Cloud Base Images`: https://fedoraproject.org/cloud/download/
.. _`DNS SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/dns/
.. _`ec2instances.info`: https://ec2instances.info/
.. _`helper playbook repository`: https://github.com/fedora-copr/ansible-fedora-copr
.. _`playbook SOP`: https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/ansible/
.. _`private IP change`: https://pagure.io/fedora-infra/ansible/c/6c80a870ff2a62e73da98f7607574e534369fb37
