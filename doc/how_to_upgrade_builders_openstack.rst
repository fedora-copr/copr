.. _how_to_upgrade_builders_openstack:

.. note:: There's currently no OpenStack instance in Fedora infrastructure, so
          this documentation exists for the historical reference (we might get
          another OpenStack instance in the future).


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


.. _`OpenStack images dashboard`: https://fedorainfracloud.org/dashboard/project/images/
.. _`Fedora Infra OpenStack`: https://fedorainfracloud.org
