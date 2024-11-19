.. _how_to_upgrade_builders:

How to upgrade builders
=======================

This article explains how to upgrade generate the Copr builder images (so called
"golden images") and how to migrate the Fedora Copr to them.  Namely for

- :ref:`AWS <prepare_aws_source_images>` (x86_64 and aarch64),
- :ref:`LibVirt/OpenStack <prepare_libvirt_source_images>` (x86_64 and ppc64le), and
- :ref:`IBM Cloud <prepare_ibmcloud_source_images>` (s390x).

This HOWTO page is useful for upgrading images to a newer Fedora release or
simply updating the packages contained within the builder images to the latest
versions.  This process of image "refreshing" significantly improves subsequent
VM startup times and resolves bugs.  Because when a builder machine starts from
a relatively up-to-date image, only a minimal set of tasks is required at
startup.

Keep amending this page if you find something not matching reality or
expectations.

Requirements
------------

* ssh access to `staging backend box`_
* ssh access to one of our x86_64 and ppc64le hypervisors, e.g.
  ``copr@vmhost-x86-copr01.rdu-cc.fedoraproject.org`` and
  ``copr@vmhost-p08-copr01.rdu-cc.fedoraproject.org``
* ssh access to ``batcave01.iad2.fedoraproject.org``, and sudo access there
* be in FAS group ``aws-copr``, so you can access `AWS login link`_ properly
* IBM Cloud API token assigned to the Fedora Copr team (see team's Bitwaarden)


.. _prepare_aws_source_images:

Prepare AWS source images
-------------------------

You need to find proper (official) ``ami-*`` Fedora image IDs, bound to
your desired VM location.  You can e.g. go to `Fedora Cloud Page`_ and search
for ``AWS`` images. There are different buttons for x86_64 and aarch64
architectures. Click the *List AWS EC2 region* button.

Do not launch any instance, only find an AMI ID
(e.g. ``ami-0c830793775595d4b``) for our region - we are using
N.Virginia option, aka ``us-east-1``.

Then ssh to ``root@copr-be-dev.cloud.fedoraproject.org``, and ``su - resalloc``,
and execute for ``x86_64`` arch::

    $ copr-resalloc-aws-new-x86_64 \
        --initial-preparation --create-snapshot-image --debug \
        --name copr-builder-image-x86_64 \
        --instance-type=c7i.xlarge \
        --ami <ami_ID>
    ...
     * Image ID: ami-0ebce709a474af685
    ...

And then also for ``aarch64``.  Note that we need an additional volume that will
be later inherited by all machines instatiated from the snapshot *ami* image (so
we don't need yet another additional volume when starting builders)::

    $ copr-resalloc-aws-new-aarch64 \
        --initial-preparation --create-snapshot-image --debug \
        --additional-volume-size 160 \
        --name copr-builder-image-aarch64 \
        --instance-type=c7g.xlarge \
        --ami <ami_ID>
    ...
     * Image ID: ami-0942a35ec3999e00d
    ...

Continue fixing the scripts/playbooks/fedora till you succeed like that ^^.
Repeat the previous steps.

The remaining step is to configure ``copr_builder_images.aws.{aarch64,x86_64}``
options in `Ansible git repo`_, in file ``inventory/group_vars/copr_dev_aws``
and reprovision the ``copr-be-dev`` instance, see :ref:`Testing`.  Document the
previous ``ami-*`` variants as ``n-1``, and remove the previous ``n-2`` images
in `EC2 console <AWS login link>`_.


.. _prepare_libvirt_source_images:

Prepare libvirt source images
-----------------------------

We prepare the LibVirt images directly on our hypervisors.  We start with the
official Fedora images as the "base images", and just modify them (this is
easier for us compared to generating images from scratch).

.. note::
   While the Power9 architecture family is required for ppc64le builds
   for Enterprise Linux 9 (or newer), we and while we only have Power8 machines
   in-house (Fedora lab) - this is none issue.  The generated images on Power8
   machines are compatible with Power9 (currently hosted in the `OSU Open Source
   Lab`_).  When uploading the image (see below), the image is as well as as
   onto LibVirt hypervisors automatically uploaded into the OSUOSL OpenStack.

Find source images
^^^^^^^^^^^^^^^^^^

The first thing you need to figure out is what image should you use for
particular architecture, and where to get it. The Cloud Base images can be
obtained on `Fedora Cloud page`_.  Pick the variants with ``.qcow2`` extension,
without the ``UKI`` mark.  Some images might be found on the `Alternate
Architectures page`_.

.. warning::
    Don't confuse PPC64LE with PPC64!

If neither of those URLs above provide the expected cloud image for the desired
Fedora version (yet), there should exist at least a "compose" version in `Koji
compose directory listing`_, look for the
``latest-Fedora-Cloud-<VERSION>/compose/Cloud/<ARCH>/images`` directory.

Image preparation
^^^^^^^^^^^^^^^^^

We can not prepare the images cross-arch, yet we need to prepare one image for
every supported architecture (on an appropriate hypervisor).  So in turn we need
to repeat the instructions for each architecture we have hypervisors for
(currently x86_64 and ppc64le).

All the hypervisors in the Fedora Copr build system are appropriately configured
for this task, so it doesn't matter which of the hypervisors is chosen (only the
architecture must match).

.. note::

    You still might need to re-run `hypervisor playbooks <hypervisors>`_ first
    to sync the "provision" configuration.

Our hypervisors have overcommitted RAM and disk space a lot (otherwise it
wouldn't be possible to start so many builders on each hypervisor in parallel).
The good thing is that we still can anytime temporarily spawn one or more VMs
for the purpose of generating the next golden image.

So let's try to generate the image from the given official Fedora Cloud image on
one of the x86_64 hypervisors::

    $ ssh copr@vmhost-x86-copr02.rdu-cc.fedoraproject.org
    [copr@vmhost-x86-copr02 ~][PROD]$ copr-image https://download.fedoraproject.org/pub/fedora/linux/releases/41/Cloud/x86_64/images/Fedora-Cloud-Base-Generic-41-1.4.x86_64.qcow2
    ... SNIP ...
    ++ date -I
    + qemu-img convert -f qcow2 /tmp/wip-image-hi1jK.qcow2 -c -O qcow2 -o compat=0.10 /tmp/copr-eimg-G6yZpG/eimg-fixed-2021-05-24.qcow2
    + cleanup
    + rm -rf /tmp/wip-image-hi1jK.qcow2

This long running task (several minutes) can fail.  If so, please fix the
script, and re-run.  Once the script finishes correctly (see above the output,
and final `eimg-fixed*.qcow` file), upload the image to all hypervisors::

    [copr@vmhost-x86-copr02 ~][PROD]$ /home/copr/provision/upload-qcow2-images /tmp/copr-eimg-G6yZpG/eimg-fixed-2021-05-24.qcow2
    ... SNIP ...
    uploaded images copr-builder-20210524_085845

Test that the image spawns correctly::

    $ ssh root@copr-be-dev.cloud.fedoraproject.org
    Last login: Fri Jun 14 12:16:48 2019 from 77.92.220.242

    # use a different spawning image for hypervisors, set the "VOLUMES.x86_64"
    # to 'copr-builder-20210524_085845'".
    [root@copr-be-dev ~][STG]# vim /var/lib/resallocserver/provision/libvirt-new

    # use a different image for the OSUOSL OpenStack.  Set the
    # `resalloc-openstack-new --image` argument to
    # 'copr-builder-20210524_085845'.
    [root@copr-be-dev ~][STG]# vim /var/lib/resallocserver/resalloc_provision/osuosl-vm

    # delete current VMs to start spawning new ones
    [root@copr-be-dev ~][STG]# su - resalloc
    Last login: Fri Jun 14 12:43:16 UTC 2019 on pts/0
    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-delete --all

    # wait a minute or so for the new VMs
    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list |grep copr_hv_ |grep STARTING
    30784 - copr_hv_x86_64_02_dev_00030784_20210524_090406 pool=copr_hv_x86_64_02_dev tags= status=STARTING releases=0 ticket=NULL

    [resalloc@copr-be-dev ~][STG]$ tail -f /var/log/resallocserver/hooks/030784_alloc
    ... SNIP ...
    DEBUG:root:Cleaning up ...
    2620:52:3:1:dead:beef:cafe:c141
    DEBUG:root:cleanup 50_shut_down_vm_destroy
    ... SNIP ...

If the log doesn't look good, you'll have to start over again (perhaps fix
spawner playbooks, or the ``copr-image`` script).  But if you see the VM IP
address (can be an IPv6 one), you are mostly done::

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep 00145
    145 - aarch64_01_dev_00000145_20190614_124441 pool=aarch64_01_dev tags=aarch64 status=UP

For ``copr_builder_images.osuosl.ppc64le`` we will use the same buidler image as
for hypervisor ppc64le.


.. _prepare_ibmcloud_source_images:

Prepare the IBM Cloud images
----------------------------

For IBM Cloud we prepare a ``qcow2``, ``s390x`` image.  This is very similar to
the :ref:`LibVirt <prepare_libvirt_source_images>` case above — notable
difference is that we don't have a native hypervisor to run the scripts on.

Fortunately, the `Z Architecture`_ virtual machines we start in IBM Cloud give
us a possibility to run the scripting directly on the VMs (nested virt support).
So we use Copr Backend machine as a hop-box — to work on one of our builder
machines::

    $ ssh root@copr-be-dev.cloud.fedoraproject.org
    # su - resalloc
    $ copr-prepare-s390x-image-builder
    ... takes one s390x builder ...
    ... installs additional packages ...
    ... does some preparation, and says ...
    Now you can start the work on the machine:
    $ ssh root@165.192.137.98
    ...

So we can switch to the builder machine::

    $ ssh root@165.192.137.98

Now, find a ``qcow2`` image we'll be updating, take a look at the
`Alternate Architectures page`_.  At this moment you want the **s390x
Architecture** category, and **Fedora Cloud qcow2**.  Being on the remote VM,
start with::

    $ copr-image https://download.fedoraproject.org/pub/fedora-secondary/releases/35/Cloud/s390x/images/Fedora-Cloud-Base-35-1.2.s390x.qcow2
    ...
    + qemu-img convert -f qcow2 /tmp/wip-image-HkgkS.qcow2 -c -O qcow2 -o compat=0.10 /tmp/root-eimg-BlS5FJ/eimg-fixed-2022-01-19.qcow2
    ...

If you feel you need to update the s390x VM, feel free to do it (the system is
disposable)::

    dnf update -y
    reboot

From the output you see the generated image ``eimg-fixed-2022-01-19.qcow2`` —
that needs to be uploaded to IBM Cloud now, under our community account.
Unfortunately, we can not _easily_ do this from Fedora machine directly as
`ibmcloud tool is not FLOSS`_.  That's why we have prepared `container image for
uploading`_, pushed to **quay.io** service  as
``quay.io/praiskup/ibmcloud-cli``::

    $ qcow_image=/tmp/root-eimg-BlS5FJ/eimg-fixed-2022-01-19.qcow2
    $ podman_image=quay.io/praiskup/ibmcloud-cli
    $ export IBMCLOUD_API_KEY=....  # find in Bitwarden
    $ podman run -e IBMCLOUD_API_KEY --rm -ti -v $qcow_image:/image.qcow2:z $podman_image upload-image
    ....
    + ibmcloud login -r jp-tok
    ....
    Uploaded image "r022-8509865b-0347-4a00-bbfe-bb6df1c5a384"
    ("copr-builder-image-s390x-20220119-142944")

Note the image ID somewhere, will be used in Ansible inventory, as
``copr_builder_images.ibm_cloud.s390x.us_east`` value.  You can test that the
new image starts well on ``copr-be-dev``,  by::

    # su - resalloc
    $ RESALLOC_NAME=copr_ic_s390x_us_east_dev \
        /var/lib/resallocserver/resalloc_provision/ibm-cloud-vm \
        create test-machine

... but note that the first start takes some time, till the image is properly
populated!  So if the script timeouts on ssh, please re-try.

When prepared, don't forget to drop the VM we used for the image preparation::

    $ resalloc ticket-close <your_id>


.. _testing:

Testing
-------

If the images for all supported architectures are updated (according to previous
sections), the `staging copr instance`_ is basically ready for testing.  Update
the `Ansible git repo`_ for all the changes in playbooks above, and also update
the ``copr_builder_images`` option in ``inventory/group_vars/copr_dev_aws`` so
it points to correct image names.

Increment the ``copr_builder_fedora_version`` number.

Once the changes are pushed upstream, you should re-provision the backend
configuration from batcave::

    $ ssh batcave01.iad2.fedoraproject.org
    $ sudo rbac-playbook \
        -l copr-be-dev.aws.fedoraproject.org groups/copr-backend.yml \
        -t provision_config

You might well want to stop here for now, and try to test for a week or so that
the devel instance behaves sanely.  If not, consider running
:ref:`sanity_tests` (or at least try to build several packages there).

You can try to kill all the old currently unused builders, and check the spawner
log what is happening::

    [copr@copr-be-dev ~][STG]$ resalloc-maint resource-delete --unused


Production
----------

There is a substantially less work for production instance. You just need to
equivalently update the production configuration file
``./inventory/group_vars/copr_aws``, so the ``copr_builder_images`` config
points to the same image names as development instance does.  And re-run
playbook from batcave::

    $ sudo rbac-playbook \
        -l copr-be.aws.fedoraproject.org groups/copr-backend.yml \
        -t provision_config

Optionally, when you need to propagate the new images quickly, you can terminate
the old but currently unused builders by::

    $ su - resalloc
    $ resalloc-maint resource-delete --unused

Cleanup
-------

When everything is up and running the new version, do not forget to delete the
old AMIs and associated snapshots from AWS.

.. _`staging backend box`: https://copr-be-dev.cloud.fedoraproject.org
.. _`Fedora Cloud page`: https://fedoraproject.org/cloud/download
.. _`Alternate Architectures page`:  https://alt.fedoraproject.org/alt
.. _`Koji compose directory listing`: https://kojipkgs.fedoraproject.org/compose/cloud/
.. _`Ansible git repo`: https://infrastructure.fedoraproject.org/cgit/ansible.git/
.. _`staging copr instance`: https://copr.stg.fedoraproject.org
.. _`AWS login link`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
.. _`ibmcloud tool is not FLOSS`: https://github.com/IBM-Cloud/ibm-cloud-cli-release/issues/162
.. _`container image for uploading`: https://github.com/praiskup/ibmcloud-cli-fedora-container
.. _`Z Architecture`: https://www.ibm.com/it-infrastructure/z
.. _`OSU Open Source Lab`: https://osuosl.org/
