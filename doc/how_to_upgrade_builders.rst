.. _how_to_upgrade_builders:

How to upgrade builders
=======================

This article explains how to upgrade the Copr builders images in

- :ref:`AWS <prepare_aws_source_images>` (x86_64 and aarch64),
- :ref:`LibVirt/OpenStack <prepare_libvirt_source_images>` (x86_64 and ppc64le),
- :ref:`IBM Cloud <prepare_ibmcloud_source_images>` (s390x),
- |ss| :ref:`We currently don't work with OpenStack separately <how_to_upgrade_builders_openstack>` |se|.

This HOWTO is useful for upgrading images to a newer Fedora release, or for just
updating all the packages contained within the builder images.  This image
"refreshing" also significantly speeds up the following VM startup times, and
fixes bugs (when a builder virtual machine is started the image, only a limited
subset of packages is always automatically updated).

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

Then ssh to ``root@copr-be-dev.cloud.fedoraproject.org``, and ``su - resalloc``,
and execute for ``x86_64`` arch::

    $ copr-resalloc-aws-new-x86_64 \
        --initial-preparation --create-snapshot-image --debug \
        --name copr-builder-image-x86_64 \
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
        --ami <ami_ID>
    ...
     * Image ID: ami-0942a35ec3999e00d
    ...

Continue fixing the scripts/playbooks/fedora till you succeed like that ^^.
Repeat the previous steps.

The remaining step is to configure ``copr_builder_images.aws.{aarch64,x86_64}``
options in `Ansible git repo`_, in file ``inventory/group_vars/copr_back_dev_aws``
and reprovision the ``copr-be-dev`` instance, see :ref:`Testing`.


.. _prepare_libvirt_source_images:

Prepare libvirt source images
-----------------------------

We prepare the LibVirt images directly on our hypervisors.  We start with the
official Fedora images as the "base images", and just modify them (this is
easier for us compared to generating images from scratch).

The Power9 architecture (note: Power9+ is required by Enterprise Linux 9+) is
currently hosted in the `OSU Open Source Lab`_.  That is an OpenStack-based
cloud, but no special actions are needed — we are able to share the same
``.qcow2`` image generate for our other ``ppc64le`` hypervisors.  When
uploading the image (see below), the image is as well automatically uploaded to
the OSUOSL OpenStack.

Find source images
^^^^^^^^^^^^^^^^^^

The first thing you need to figure out is what image should you use and where to
get it.

The Cloud Base image for x86_64 can be obtained on `Fedora Cloud page`_.  Pick
the one with ``.qcow2`` extension.  The ppc64le and aarch64 images can be found
on the `Alternate Architectures page`_.  Don't confuse PPC64LE with PPC64.

If neither that url provides the expected cloud image version (yet), there
should exist at least a "compose" version in `Koji compose directory listing`_,
look for ``latest-Fedora-Cloud-<VERSION>/compose/Cloud/<ARCH>/images``
directory.

Image preparation
^^^^^^^^^^^^^^^^^

We can not prepare the images cross-arch, and we need to prepare one image for
every supported architecture (on an appropriate hypervisor).  So in turn we need
to repeat the instructions for each architecture we have hypervisors for
(currently x86_64 and ppc64le).

All the hypervisors in Copr build system are appropriately configured, so it
doesn't matter which of the hypervisors is chosen (only the architecture must
match).

Our hypervisors have overcommitted RAM and disk space a lot (otherwise it
wouldn't be possible to start so many builders on each hypervisor in parallel).
The good thing about that is that we can anytime temporarily spawn one or more
VMs for the purpose of generating the builder image.

So let's try to generate the image from the given official Fedora Cloud image on
one of the x86_64 hypervisors::

    $ ssh copr@vmhost-x86-copr02.rdu-cc.fedoraproject.org

    [copr@vmhost-x86-copr02 ~][PROD]$ copr-image https://download.fedoraproject.org/pub/fedora/linux/releases/34/Cloud/x86_64/images/Fedora-Cloud-Base-34-1.2.x86_64.qcow2
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

    # increase the `max_prealloc` value in one of the hypervisors and OSUOSL
    # (when testing ppc64le images) by a value 1 (e.g. 2=>3) so resalloc server
    # begins starting new machine(s)
    [root@copr-be-dev ~][STG]# vim /etc/resallocserver/pools.yaml

    # wait a minute or so for the new VMs
    [root@copr-be-dev ~][STG]# su - resalloc
    Last login: Fri Jun 14 12:43:16 UTC 2019 on pts/0

    [resalloc@copr-be-dev ~][STG]$ resalloc-maint resource-list | grep STARTING
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

    #> copr-image https://download.fedoraproject.org/pub/fedora-secondary/releases/35/Cloud/s390x/images/Fedora-Cloud-Base-35-1.2.s390x.qcow2
    ...
    + qemu-img convert -f qcow2 /tmp/wip-image-HkgkS.qcow2 -c -O qcow2 -o compat=0.10 /tmp/root-eimg-BlS5FJ/eimg-fixed-2022-01-19.qcow2
    ...

From the output you see the generated image ``eimg-fixed-2022-01-19.qcow2`` —
that needs to be uploaded to IBM Cloud now, under our community account.
Unfortunately, we can not _easily_ do this from Fedora machine directly as
`ibmcloud tool is not FLOSS`_.  That's why we have prepared `container image for
uploading`_, pushed to **quay.io** service  as
``quay.io/praiskup/ibmcloud-cli``::

    $ qcow_image=/tmp/root-eimg-BlS5FJ/eimg-fixed-2022-01-19.qcow2
    $ podman_image=quay.io/praiskup/ibmcloud-cli
    $ podman run --rm -ti -v $qcow_image:/image.qcow2:z $podman_image upload-image
    ....
    + ibmcloud login -r jp-tok -u coprteam@fedoraproject.org
    API endpoint: https://cloud.ibm.com
    Password> <use our team password here, stored in bitwaarden>
    ....
    Uploaded image "r022-8509865b-0347-4a00-bbfe-bb6df1c5a384"
    ("copr-builder-image-s390x-20220119-142944")

Note the image ID somewhere, will be used in Ansible inventory, as
``copr_builder_images.ibm_cloud.s390x`` value.  You can test that the new image
starts well on ``copr-be-dev``,  by::

    # su - resalloc
    $ /var/lib/resallocserver/resalloc_provision/ibm-cloud-vm \
        --log-level debug \
        create test-machine \
        --image-uuid r022-2a904fb5-e69c-4ba7-b5ea-d6215ba4a6ee

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

    [copr@copr-be-dev ~][STG]$ resalloc-maint resource-delete --unused


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

Optionally, when you need to propagate the new images quickly, you can terminate
the old but currently unused builders by::

    $ su - resalloc
    $ resalloc-maint resource-delete --unused

.. _`staging backend box`: https://copr-be-dev.cloud.fedoraproject.org
.. _`Fedora Cloud page`: https://alt.fedoraproject.org/cloud
.. _`Alternate Architectures page`:  https://alt.fedoraproject.org/alt
.. _`Koji compose directory listing`: https://kojipkgs.fedoraproject.org/compose/cloud/
.. _`Ansible git repo`: https://infrastructure.fedoraproject.org/cgit/ansible.git/
.. _`staging copr instance`: https://copr.stg.fedoraproject.org
.. _`AWS login link`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
.. _`ibmcloud tool is not FLOSS`: https://github.com/IBM-Cloud/ibm-cloud-cli-release/issues/162
.. _`container image for uploading`: https://github.com/praiskup/ibmcloud-cli-fedora-container
.. _`Z Architecture`: https://www.ibm.com/it-infrastructure/z
.. _`OSU Open Source Lab`: https://osuosl.org/
