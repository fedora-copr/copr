.. _how_to_upgrade_builders:

How to upgrade builders
=======================

This article explains how to upgrade the Copr builders in OpenStack (ppc64le,
x86_64), AWS (x86_64 and aarch64) and libvirt (aarch64) to a newer Fedora once
it is released.

Keep amending this page if you find something not matching reality or expectations.


.. note:: Until a datacenter migration is done, our builders run only in
          Amazon AWS. You can safely jump to :ref:`prepare_aws_source_images`.
          Also, ``ppc64le`` builders are temporarily disabled.


Requirements
------------

* ssh access to `staging backend box`_
* an account on `Fedora Infra OpenStack`_, ..
* downloaded OpenStack RC File (go to OpenStack dasboard -- Access & Security --
  API Access -- Download OpenStack RC File) ..
* and ``python3-openstackclient`` package installed
* ssh access to the main aarch64 hypervisor
  ``copr@virthost-aarch64-os01.fedorainfracloud.org``
* ssh access to ``batcave01.iad2.fedoraproject.org``, and sudo access there
* be in FAS group ``aws-copr``, so you can access `AWS login link`_ properly


Find source images
------------------

The first thing you need to figure out is what image should you use and where to
get it.

The Cloud Base image for x86_64 can be obtained on `Fedora Cloud page`_.  Pick
the one with ``.qcow2`` extension.  The ppc64le and aarch64 images can be found
on the `Alternate Architectures page`_.  Don't confuse PPC64LE with PPC64.

If neither that url provides the expected cloud image version (yet), there
should exist at least a "compose" version in `Koji compose directory listing`_,
look for ``latest-Fedora-Cloud-<VERSION>/compose/Cloud/<ARCH>/images``
directory.


Prepare OpenStack source images
-------------------------------

(x86_64 and ppc64le architectures)

For OpenStack, there is an image registry on `OpenStack images dashboard`_.  By
default you see only the project images; to see all of them, click on the
``Public`` button.

Search for the ``Fedora-Cloud-Base-*`` images of the particular Fedora.  Are
both x86_64 and ppc64le images available?  Then you can jump right to the next
section.

Download the image, and upload it to the infra OpenStack.  Be careful to keep
sane ``Fedora-Cloud-Base*`` naming, and to make it public, so others can later
use it as well:

::

    $ wget <THE_QCOW_IMAGE_URL>
    .. downloaded Fedora-Cloud-Base-30-1.2.x86_64.qcow2 ..
    $ source <THE_OPENSTACK_RC_FILE>
    # hw_rng_model=virtio is needed to guarantee enough entropy on VMs
    # --public is needed to publish it to everyone
    # --protected so other openstack users can not delete it
    $ openstack image create \
        --file Fedora-Cloud-Base-30-1.2.x86_64.qcow2 \
        --public \
        --protected \
        --disk-format qcow2 \
        --container-format bare \
        --property architecture=x86_64 \
        --property hw_rng_model=virtio \
        Fedora-Cloud-Base-30-1.2.x86_64

Note also the ``--property hw_rng_model=virtio`` option which guarantees that
the VMs won't wait indefinitely for random seed.


Prepare VM for snapshot
^^^^^^^^^^^^^^^^^^^^^^^

Open a ssh connection to ``copr-be-dev.cloud.fedoraproject.org`` and run::

    # su - copr
    $ copr-builder-image-prepare-cloud.sh os:x86_64 Fedora-Cloud-Base-30-1.2.x86_64 # or ppc64le
    ... snip ...
    TASK [disable offloading] *****************************************************
    Wednesday 14 August 2019  13:31:27 +0000 (0:00:05.603)       0:03:47.402 ******
    changed: [172.25.150.72]
    ... snip ....

It can fail (for various reasons, missing packages, changes in Fedora, etc.).
But after running the script, you will get an IP address of a spawned builder.
You can ssh into that builder, make changes and try to debug.  Then, knowing
where the problem is - fix the following playbook files::

    /home/copr/provision/provision_builder_tasks.yml
    /home/copr/provision/builderpb_nova.yml
    /home/copr/provision/builderpb_nova_ppc64le.yml

Repeat the fixing of playbooks till the script finishes properly::

    $ copr-builder-image-prepare-cloud.sh os:x86_64 Fedora-Cloud-Base-30-1.2.x86_64
    ... see the output instructions ...
    TASK [disable offloading] *****************************************************
    Wednesday 14 August 2019  13:31:27 +0000 (0:00:05.603)       0:03:47.402 ******
    changed: [172.25.150.72]
    ... snip ....
    Request to stop server Copr_builder_20901443 has been accepted.
    Please go to https://fedorainfracloud.org/ page, log-in and find the instance

        Copr_builder_20901443

    Check that it is in SHUTOFF state.  Create a snapshot from that instance, name
    it "copr-builder-x86_64-f30-20190814_133128".  Once snapshot is saved, run:

        $ copr-builder-image-fixup-snapshot-os.sh copr-builder-x86_64-f30-20190814_133128

    And continue with
    https://docs.pagure.org/copr.copr/how_to_upgrade_builders.html#how-to-upgrade-builders

Once done, continue with the manual steps from the instructions on the
command-line output (create image snapshot and run the
``copr-builder-image-fixup-snapshot-os.sh`` script).   Those manual steps could be done
automatically, but `Fedora Infra OpenStack`_ refuses snapshot API requests for
some reason.


Finishing up OpenStack images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Since you have a new image name(s) which can be used on builders, you can
configure ``copr_builder_images`` option in
``/home/copr/provision/nova_cloud_vars.yml`` variable file.  Since now, the
**development** backend should spawn from new image.  You can try to kill all
the old builders, and check the spawner log what is happening::

    [copr@copr-be-dev ~][STG]$ cleanup_vm_nova.py --kill-also-unused
    [copr@copr-be-dev ~][STG]$  tail -f /var/log/copr-backend/spawner.log

Try to build some packages and you are done.


.. _prepare_aws_source_images:

Prepare AWS source images
-------------------------

You need to find proper (official) ``ami-*`` Fedora image IDs, bound to
your desired VM location.  You can e.g. go to `Fedora Cloud Page`_ and search
for ``GP2 HVM AMIs`` (for x86_64) and ``arm64 AMIs`` (for aarch64) sections.

You should see there the *Click to launch* buttons.  When you click on them a
new window should appear (javascript) with a list of available server locations.
So you see the small "blue cloud" icon/hyperlink related to the desired server
location (we are using N.Virginia option, aka ``us-east-1``, but we should move
to ``us-west-*`` soon).

Do not click the launch button and do not proceed to launch the instance
manually through Amazon AWS launcher. Only remember the
``ami-0c830793775595d4b`` ID part.

Then ssh to ``root@copr-be-dev.cloud.fedoraproject.org``, and ``su - copr``, and
execute::

    $ copr-builder-image-prepare-cloud.sh aws:aarch64 ami-0c830793775595d4b
    ... snip output ...
    The new image ID   is: ami-XXXXXXXXXXXXXXXXX
    The new image Name is: copr-builder-aarch64-f31-20191203_110334

Continue fixing the script/playbooks/fedora till you succeed like that.  Repeat
the previous steps for both ``aarch64`` and ``x86_64``.

The remaining step is to configure ``copr_builder_images.aws.{aarch64,x86_64}``
options in `Ansible git repo`_, in file ``inventory/group_vars/copr_back_dev_aws``
and reprovision the ``copr-be-dev`` instance, see :ref:`Testing`.


Prepare libvirt source images
-----------------------------

(aarch64 architecture only)

We can not prepare the image locally (on x86 laptops), so we have to create it
on some remote aarch64 box.  We have currently two aarch64 hypervisors available
for Copr project purposes, and we'll use one of them.

The problem is that both the aarch64 hypervisors are configured so they are
using all the availalbe resources (namely storage), we have to kill some
pre-existing VMs first to have some space (note the ``_dev`` keyword, we are not
deleting production builders in this step!)::

    $ ssh root@copr-be-dev.cloud.fedoraproject.org

    # set 'aarch64_01_dev.max' option to 0 to disable spawner on hypervisor 1
    [root@copr-be-dev ~][STG]# vim /etc/resallocserver/pools.yaml

    # and terminate all already running resources there;  if there are some
    # STARTING instances, please wait till they are not UP
    [root@copr-be-dev ~][STG]# su - resalloc
    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep aarch64_01_dev
    138 - aarch64_01_dev_00000138_20190613_051611 pool=aarch64_01_dev tags=aarch64 status=UP
    140 - aarch64_01_dev_00000140_20190613_051613 pool=aarch64_01_dev tags=aarch64 status=UP

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-delete 138 140

    # check that all are deleted (no output)
    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep aarch64_01_dev

Now begin the work on the aarch64 box:

::

    $ ssh copr@virthost-aarch64-os01.fedorainfracloud.org

    # just in case you wanted to call /bin/virsh directly in this session
    [copr@virthost-aarch64-os01 ~][PROD]$ export VIRSH_DEFAULT_CONNECT_URI=qemu:///system

Download the image, and prepare it for upload

::

    [copr@virthost-aarch64-os01 ~][PROD]$ wget --directory-prefix=/tmp \
        https://mirrors.nic.cz/fedora/linux/releases/30/Cloud/aarch64/images/Fedora-Cloud-Base-30-1.2.aarch64.qcow2

    [copr@virthost-aarch64-os01 ~][PROD]$ cd ~/vm-manage

    # prepare the image, it takes ~15 minutes
    [copr@virthost-aarch64-os01 ~][PROD]$ ./prepare-disk /tmp/Fedora-Cloud-Base-30-1.2.aarch64.qcow2
    ...
    + cp /tmp/Fedora-Cloud-Base-30-1.2.aarch64.qcow2 /tmp/newdisk.qcow2
    ...

This can fail, if so, please fix the script, and re-run.  Once done, upload the
image to libvirt instances (both hypervisors)::

    [copr@virthost-aarch64-os01 vm-manage][PROD]$ ./upload-disk /tmp/newdisk.qcow2
    ...
    + virsh ... vol-upload copr-builder-20190614_123554 ... /tmp/newdisk.qcow2
    ...
    uploaded images copr-builder-20190614_123554

Test that the image spawns correctly::

    $ ssh root@copr-be-dev.cloud.fedoraproject.org
    Last login: Fri Jun 14 12:16:48 2019 from 77.92.220.242

    # use a different image, set the "img_volume = 'copr-builder-20190614_123554'"
    [root@copr-be-dev ~][PROD]# vim /var/lib/resallocserver/resalloc_provision/vm-aarch64-new

    # re-enable spawner, set 'aarch64_01_dev.max' option to 2
    [root@copr-be-dev ~][STG]# vim /etc/resallocserver/pools.yaml

    # wait a minute for newly spawned VMs
    [root@copr-be-dev ~][STG]# su - resalloc
    Last login: Fri Jun 14 12:43:16 UTC 2019 on pts/0

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list
    141 - aarch64_02_dev_00000141_20190613_051613 pool=aarch64_02_dev tags=aarch64 status=UP
    139 - aarch64_02_dev_00000139_20190613_051611 pool=aarch64_02_dev tags=aarch64 status=UP
    144 - aarch64_01_dev_00000144_20190614_124441 pool=aarch64_01_dev tags= status=STARTING
    145 - aarch64_01_dev_00000145_20190614_124441 pool=aarch64_01_dev tags= status=STARTING

    [resalloc@copr-be-dev ~][STG]$ tail -f /var/log/resallocserver/hooks/000145_alloc
    ...
    DEBUG:root: -> exit_status=0, time=233.029s
    DEBUG:root:cleaning up workdir
    38.145.48.106


If the log doesn't look good, you'll have to start over again (perhaps fix
spawner playbooks, or the ``prepare-disk`` script).  But if you see the VM IP
address, you are mostly done::

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep 00145
    145 - aarch64_01_dev_00000145_20190614_124441 pool=aarch64_01_dev tags=aarch64 status=UP


.. _testing:

Testing
-------

If the images for all supported architectures are updated (according to previous
sections), the `staging copr instance`_ is basically ready for testing.  Update
the `Ansible git repo`_ for all the changes in playbooks above, and also update
the ``copr_builder_images`` option in ``inventory/group_vars/copr_back_dev`` so
it points to correct image names.  Once the changes are pushed upstream, you
should re-provision the backend configuration from batcave::

    $ ssh batcave01.iad2.fedoraproject.org
    $ sudo rbac-playbook \
        -l copr-be-dev.aws.fedoraproject.org groups/copr-backend.yml \
        -t provision_config

You might well want to stop here for now, and try to test for a week or so that
the devel instance behaves sanely.  If not, consider running
:ref:`sanity_tests` (or at least try to build several packages there).

You can try to kill all the old currently unused builders, and check the spawner
log what is happening::

    [copr@copr-be-dev ~][STG]$ cleanup_vm_nova.py --kill-also-unused
    [copr@copr-be-dev ~][STG]$ cleanup-vms-aws --kill-also-unused
    [copr@copr-be-dev ~][STG]$ tail -f /var/log/copr-backend/spawner.log


Production
----------

There is a substantially less work for production instance. You just need to
equivalently update the production configuration file
``./inventory/group_vars/copr_back``, so the ``copr_builder_images`` config
points to the same image names as development instance does.  And re-run
playbook from batcave::

    $ sudo rbac-playbook \
        -l copr-be.aws.fedoraproject.org groups/copr-backend.yml \
        -t provision_config

Optionally, when you need to propagate the builders quickly, you can terminate
the old currently unused builders by::

    $ cleanup_vm_nova.py --kill-also-unused
    $ cleanup-vms-aws --kill-also-unused

.. _`staging backend box`: https://copr-be-dev.cloud.fedoraproject.org
.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`Fedora Cloud page`: https://alt.fedoraproject.org/cloud
.. _`Alternate Architectures page`:  https://alt.fedoraproject.org/alt
.. _`Koji compose directory listing`: https://kojipkgs.fedoraproject.org/compose/cloud/
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
.. _`Ansible git repo`: https://infrastructure.fedoraproject.org/cgit/ansible.git/
.. _`staging copr instance`: https://copr-fe-dev.cloud.fedoraproject.org
.. _`AWS login link`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
