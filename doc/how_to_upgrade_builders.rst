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
* ssh access to ``batcave01.iad2.fedoraproject.org``, and sudo access there
* access to `Konflux tenant`_ where we build images
* be in FAS group ``aws-copr``, so you can access `AWS login link`_ properly


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

We have set up a GitOps process, so you may simply commit to the
`image building repo`_ to trigger a new multi-arch OCI image build in Konflux.

Alternatively, go to this `Konflux component`_, click on the "Actions" tab, and
then select "Start a new build."  This will build OCI images for all
architectures.  Wait until it is finished, and then continue and build bootable
images.

Locate the built image ID in Konflux UI
---------------------------------------

Check the last "push" Pipelinerun, and go to the "Details" tab.  You should find
the ``IMAGE_URL`` field that you want to copy-paste.  If the pipeline failed but
at least the ``build-image-index`` Task succeeded, go to the "Details" tab on
that Task and copy the ``IMAGE_URL`` from there.  Example of such URL::

    IMAGE_URL=quay.io/fedora/fedora-bootc:42@sha256:be629db2ab373c054d8f611a214d21b6e16ce48118068d47cb2f1f87a0e30cfa

.. _prepare_libvirt_source_images:

.. _prepare_aws_source_images:

.. _prepare_ibmcloud_source_images:


Prepare the images on staging backend machine
---------------------------------------------

This step allocates arch-specific VMs, creates qcow2/raw/ami images on them, and
downloads them back to a directory structured as ``/var/lib/copr/public_html/images/2025-07-28/``::

   $ ssh root@copr-be-dev.aws.fedoraproject.org
   # su - resalloc
   $ test -d copr-image-builder || git clone https://github.com/fedora-copr/copr-image-builder
   $ cd copr-image-builder && git pull
   $ make IMAGE=$IMAGE_URL<from the previous step>
   ... takes ~1h ...


Upload the images
-----------------

Now it's time to upload the built images to appropriate places::

    stamp=`date -I` /var/lib/resallocserver/provision/upload-qcow2-images-be /var/lib/copr/public_html/images/2025-07-25

Check the stdout/stderr of the upload script, and recall image IDs.

Make sure you tag the images in EC2::

    for image in ami-09a868e2b78e77457 ami-01e3532773eff119c ami-01e3532773eff119c ; do
    aws ec2 create-tags --resources "$image" --tags Key=FedoraGroup,Value=copr --region us-east-1
    done

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
.. _`Konflux tenant`: https://konflux-ui.apps.kflux-prd-rh02.0fk9.p1.openshiftapps.com/ns/fedora-copr-tenant/applications/fedora-copr-builder
.. _`image building repo`: https://github.com/fedora-copr/copr-image-builder
