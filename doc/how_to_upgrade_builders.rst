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



Building an image locally
-------------------------

This is useful for development or debugging but the produced image will not be
used production.

::

   $ git clone https://github.com/fedora-copr/copr-image-builder.git
   $ cd copr-image-builder
   $ IMAGE_TYPE=qcow2 BUILD_OCI=true ./copr-build-image-bootc.sh

Run ``virt-manager`` and boot the image.


Build OCI images in Konflux
---------------------------

Go to this `Konflux component`_ and click ``Actions > Start a new build``.
It will build OCI images for all architectures. Wait until it is finished and
then continue and build bootables images.


.. _prepare_libvirt_source_images:

x86_64 qcow2
------------

::

   $ ssh root@copr-be-dev.aws.fedoraproject.org
   # su - resalloc
   $ resalloc ticket --tag hypervisor_x86_64
   $ resalloc ticket-wait 751
   $ IP=2620:52:3:1:dead:beef:cafe:c1c1
   $ ssh root@$IP
   # git clone https://github.com/fedora-copr/copr-image-builder.git
   # cd copr-image-builder
   # ./prepare-worker
   # IMAGE_TYPE=qcow2 BUILD_OCI=false IMAGE=quay.io/redhat-user-workloads/fedora-copr-tenant/copr-image-builder ./copr-build-image-bootc.sh
   # exit
   $ scp -6 root@[$IP]:/root/copr-image-builder/output/qcow2/disk.qcow2 /var/lib/copr/public_html/images/disk.x86_64.qcow2
   $ resalloc ticket-close 751

   $ scp /var/lib/copr/public_html/images/disk.x86_64.qcow2 copr@vmhost-x86-copr02.rdu-cc.fedoraproject.org:/tmp/disk.qcow2
   $ ssh copr@vmhost-x86-copr02.rdu-cc.fedoraproject.org
   $ /home/copr/provision/upload-qcow2-images /tmp/disk.qcow2
   $ rm /tmp/disk.qcow2
   $ exit


.. _prepare_aws_source_images:

x86_64 AMI
----------

::

   $ ssh root@copr-be-dev.aws.fedoraproject.org
   # su - resalloc
   $ resalloc ticket --tag hypervisor_x86_64
   $ resalloc ticket-wait 751
   $ IP=2620:52:3:1:dead:beef:cafe:c1c1
   $ ssh root@$IP
   # git clone https://github.com/fedora-copr/copr-image-builder.git
   # cd copr-image-builder
   # ./prepare-worker
   # IMAGE_TYPE=ami BUILD_OCI=false IMAGE=quay.io/redhat-user-workloads/fedora-copr-tenant/copr-image-builder ./copr-build-image-bootc.sh
   # exit
   $ scp -6 root@[$IP]:/root/copr-image-builder/output/image/disk.raw /var/lib/copr/public_html/images/disk.x86_64.raw
   $ resalloc ticket-close 751

   $ image-builder upload \
       /var/lib/copr/public_html/images/disk.x86_64.raw \
       --to aws \
       --aws-ami-name copr-builder-image-bootc-$(date +"%Y%m%d-%H%M%S")-x86_64 \
       --aws-region us-east-1 \
       --aws-bucket copr-images


aarch64
-------

::

   $ ssh root@copr-be-dev.aws.fedoraproject.org
   # su - resalloc
   $ resalloc ticket --tag arch_aarch64_native
   $ resalloc ticket-wait 751
   $ IP=100.26.46.8
   $ ssh root@$IP
   # git clone https://github.com/fedora-copr/copr-image-builder.git
   # cd copr-image-builder
   # ./prepare-worker
   # IMAGE_TYPE=ami BUILD_OCI=false IMAGE=quay.io/redhat-user-workloads/fedora-copr-tenant/copr-image-builder ./copr-build-image-bootc.sh
   # exit
   $ scp root@$IP:/root/copr-image-builder/output/image/disk.raw /var/lib/copr/public_html/images/disk.aarch64.raw
   $ resalloc ticket-close 751

   $ image-builder upload \
       /var/lib/copr/public_html/images/disk.aarch64.raw \
       --arch aarch64 \
       --to aws \
       --aws-ami-name copr-builder-image-bootc-$(date +"%Y%m%d-%H%M%S")-aarch64 \
       --aws-region us-east-1 \
       --aws-bucket copr-images


ppc64le
-------

::

   $ ssh root@copr-be-dev.aws.fedoraproject.org
   # su - resalloc
   $ resalloc ticket --tag hypervisor --tag arch_ppc64le
   $ resalloc ticket-wait 751
   $ IP=2620:52:3:1:dead:beef:cafe:c1c1
   $ ssh root@$IP
   # git clone https://github.com/fedora-copr/copr-image-builder.git
   # cd copr-image-builder
   # ./prepare-worker
   # IMAGE_TYPE=qcow2 BUILD_OCI=false IMAGE=quay.io/redhat-user-workloads/fedora-copr-tenant/copr-image-builder ./copr-build-image-bootc.sh
   # exit
   $ scp -6 root@[$IP]:/root/copr-image-builder/output/qcow2/disk.qcow2 /var/lib/copr/public_html/images/disk.ppc64le.qcow2
   $ resalloc ticket-close 751

   $ scp /var/lib/copr/public_html/images/disk.ppc64le.qcow2 copr@vmhost-p08-copr01.rdu-cc.fedoraproject.org:/tmp/disk.qcow2
   $ ssh copr@vmhost-p08-copr01.rdu-cc.fedoraproject.org
   $ /home/copr/provision/upload-qcow2-images /tmp/disk.qcow2
   $ rm /tmp/disk.qcow2
   $ exit


.. _prepare_ibmcloud_source_images:

s390x
-----

::

   $ ssh root@copr-be-dev.aws.fedoraproject.org
   # su - resalloc
   $ resalloc ticket --tag arch_s390x_native
   $ resalloc ticket-wait 751
   $ IP=13.116.88.91
   $ ssh root@$IP
   # git clone https://github.com/fedora-copr/copr-image-builder.git
   # cd copr-image-builder
   # ./prepare-worker
   # IMAGE_TYPE=qcow2 BUILD_OCI=false IMAGE=quay.io/redhat-user-workloads/fedora-copr-tenant/copr-image-builder ./copr-build-image-bootc.sh
   # exit
   $ scp root@$IP:/root/copr-image-builder/output/qcow2/disk.qcow2 /var/lib/copr/public_html/images/disk.s390x.qcow2
   $ resalloc ticket-close 751

   $ exit
   # qcow_image=/var/lib/copr/public_html/images/disk.s390x.qcow2
   # podman_image=quay.io/praiskup/ibmcloud-cli
   # export IBMCLOUD_API_KEY=....  # find in Bitwarden
   # podman run -e IBMCLOUD_API_KEY --rm -ti --network=slirp4netns -v $qcow_image:/image.qcow2:z $podman_image upload-image



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
.. _`Konflux component`: https://konflux-ui.apps.kflux-prd-rh02.0fk9.p1.openshiftapps.com/ns/fedora-copr-tenant/applications/fedora-copr-builder/components/copr-image-builder
