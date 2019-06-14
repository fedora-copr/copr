.. _how_to_upgrade_builders:

How to upgrade builders
=======================

This article explains how to upgrade the Copr builders in OpenStack (ppc64le,
x86_64) and libvirt (aarch64) to a newer Fedora once it is released.

Keep amending this page if you find something not matching reality or expectations.


Requirements
------------

* ssh access to `staging backend box`_
* an account on `Fedora Infra OpenStack`_, ..
* downloaded OpenStack RC File (go to OpenStack dasboard -- Access & Security --
  API Access -- Download OpenStack RC File) ..
* and ``python3-openstackclient`` package installed
* ssh access to the main aarch64 hypervisor
  ``copr@virthost-aarch64-os01.fedorainfracloud.org``


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

Open a ssh connection to ``copr-be-dev.cloud.fedoraproject.org`` and edit the
``/home/copr/provision/builderpb_nova.yml`` playbook (resp.
``/home/copr/provision/builderpb_nova_ppc64le.yml`` for ppc64le variant).  There
is the following part

.. _prepare_base_image:

::

    vars:
      # pass this options if you need to create new base image from snapshot
      prepare_base_image: False

Set the ``prepare_base_image`` variable to ``True``. In the same file, there is also a section that looks like this

.. _image_name:

::

    vars:
      ...
      image_name: "Fedora-Cloud-Base-26_Beta-1.4.x86_64"

Update the image name to the one that in the first step you decided to use. Now, run the playbook as the ``copr`` user and see what happens. It is also a good idea to temporarily stop the ``copr-backend``.

::

    systemctl stop copr-backend
    su copr
    ansible-playbook /home/copr/provision/builderpb_nova.yml

It can likely fail (for various reasons, missing packages, changes in Fedora,
etc.).  Continue to next paragraph to see how to solve this problem.

After running the ``builderpb_nova.yml`` playbook, you will get an IP address of
a spawned builder.  You can ssh into that builder, make changes and then create
a snapshot (i.e. image) from that builder.  To fix the previous issue with
missing python package, run

::

    [copr@copr-be-dev ~][STG]$ ssh fedora@172.XX.XXX.XXX
    [fedora@172.XX.XXX.XXX ~]$ sudo dnf install python


Creating a snapshot
^^^^^^^^^^^^^^^^^^^

Open the `OpenStack instances dashboard`_.  Make sure that your "Current
Project" is the project that you expect (``coprdev``).  There are many instances
so how can you be a hundred percent sure which one you modified?  Use the IP
address as an identifier.

Optionally, click on ``More -> Shut Off Instance`` for that instance (sometimes
it happens that OpenStack doesn't allow us to create snapshot from running
instance).

Click on ``More -> Create Snapshot`` for that instance.

Set snapshot name to something like ``copr-builder-x86_64-f27``. It can be a little tricky though. When you are not creating a first snapshot for the particular release, there might be an older snapshot with the same name, because the names don't have to be unique. You need to delete the older one.

In addition, make sure to make the snapshot Public, so we can use it also for production servers and Protected, so other people can't delete it.

Configure also the snapshot image to use emulated "hardware" random generator
(otherwise with our OpenStack and new guest kernels the boot would take insanely
long on gathering entropy):

::

    $ openstack image set --property hw_rng_model=virtio <THE_SNAPSHOT_UUID>


Edit the ``builderpb_nova.yml`` playbook as you did in the :ref:`previous section <image_name>` and set the new image name. Now run the playbook again

::

    [copr@copr-be-dev ~][STG]$ ansible-playbook /home/copr/provision/builderpb_nova.yml

Iterate this process until it ends successfully.



Finishing up OpenStack images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Once you successfully provisioned a builder, you are almost done. First, create a snapshot of that builder.
We learned how to do that in the previous section. Then set the :ref:`prepare_base_image <prepare_base_image>`
back to ``False``.

Throw away the builders that the backend is currently using and let it load new ones from the new image.

::

    [copr@copr-be-dev ~][STG]$ redis-cli
    127.0.0.1:6379> FLUSHALL
    [copr@copr-be-dev ~][STG]$ /home/copr/cleanup_vm_nova.py
    [copr@copr-be-dev ~][STG]$ copr-backend-service start

Try to build some packages and you are done.


Prepare libvirt source images
-----------------------------

(aarch64 architecture only)

We can not prepare the image locally (on x86 laptops), so we have to create it
on some remote aarch64 box.  Since we have two aarch64 hypervisors for Copr now,
so we'll work with one of them.  But since the aarch64 hypervisors are
configured so they are using all the availalbe resources (namely disks), we have
to have some VMs shut down first to have some space (note the ``_dev`` keyword,
we are not deleting production builders in this step):

::

    $ ssh root@copr-be-dev.cloud.fedoraproject.org
    # set 'aarch64_01_dev.max' option to 0 to disable spawner on hypervisor 1

    [root@copr-be-dev ~][STG]# vim /etc/resallocserver/pools.yaml

    # and terminate all already running resources there;  if there are some
    # STARTING instances, please wait till they are not UP
    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep aarch64_01_dev
    138 - aarch64_01_dev_00000138_20190613_051611 pool=aarch64_01_dev tags=aarch64 status=UP
    140 - aarch64_01_dev_00000140_20190613_051613 pool=aarch64_01_dev tags=aarch64 status=UP

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-delete 138 140

    # check that all are deleted (no output)
    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep aarch64_01_dev

Now start the work on the aarch64 box:

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

Upload the image to libvirt instances:

::

    [copr@virthost-aarch64-os01 vm-manage][PROD]$ ./upload-disk /tmp/newdisk.qcow2
    ...
    + virsh ... vol-upload copr-builder-20190614_123554 ... /tmp/newdisk.qcow2
    ...
    uploaded images copr-builder-20190614_123554

Test that the image spawns correctly:

::

    $ ssh root@copr-be-dev.cloud.fedoraproject.org
    Last login: Fri Jun 14 12:16:48 2019 from 77.92.220.242

    # temporarily use different image, set the option:
    # img_volume = 'copr-builder-20190614_123554'
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
address, you are mostly done:

::

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep 00145
    145 - aarch64_01_dev_00000145_20190614_124441 pool=aarch64_01_dev tags=aarch64 status=UP

Reset the temporary image back to ``img_volume=copr-builder``:

::

    [resalloc@copr-be-dev ~][STG]$ exit
    [root@copr-be-dev ~][PROD]# vim /var/lib/resallocserver/resalloc_provision/vm-aarch64-new

Swap the image-names in hypervisors:

::

    $ ssh copr@virthost-aarch64-os01.fedorainfracloud.org
    [copr@virthost-aarch64-os01 ~][PROD]$ cd ~/vm-manage

    [copr@virthost-aarch64-os01 ~][PROD]$ ./promote-disk copr-builder-20190614_123554
    ...
    copr-builder == copr-builder-20190614_123554 now

Done.  You can still kill all VMs by ``resalloc-maint resource-delete ...``, but
if you are not in hurry - old VMs will slowly get terminated - and all the new
VMs will be started from the freshly updated ``copr-builder`` image.


Production
----------

There is a substantially less work for production instance. You just need to
edit this playbook (and only for x86_64 and ppc64le images)

https://infrastructure.fedoraproject.org/cgit/ansible.git/tree/roles/copr/backend/files/provision/builderpb_nova.yml

and update the `image_name` variable to the name of our new snapshot (e.g. copr-builder-x86_64-f27).
Then you need to commit the change and push it to the repository. If you don't have a write permission for it, then
ask someone who does.

Once the change is pushed, you need to re-provision the backend instance or ask someone to do it:

::

    rbac-playbook groups/copr-backend.yml -t provision_config


.. _`staging backend box`: https://copr-be-dev.cloud.fedoraproject.org
.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
.. _`Fedora Cloud page`: https://alt.fedoraproject.org/cloud
.. _`Alternate Architectures page`:  https://alt.fedoraproject.org/alt
.. _`Koji compose directory listing`: https://kojipkgs.fedoraproject.org/compose/cloud/
.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`OpenStack instances dashboard`: https://fedorainfracloud.org/dashboard/project/instances/
