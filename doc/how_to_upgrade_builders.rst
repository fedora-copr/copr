.. _how_to_upgrade_builders:

How to upgrade builders
=======================

This article explains how to upgrade the Copr builders in OpenStack to a newer Fedora once it is released.

Keep amending this page if you find something not matching reality or expectations.


Requirements
------------

* ssh access to copr-be-dev.cloud.fedoraproject.org
* an account on https://fedorainfracloud.org, and
* OpenStack RC File for that ^^ account for `coprdev` tenant


Provide the image
-----------------

The first thing you need to figure out is what image should you use and where to get it. Luckily there is an image registry on https://fedorainfracloud.org/dashboard/project/images/. By default you see only the project images, to see all of them, click on the ``Public`` button.

Search for the ``Fedora-Cloud-Base-*`` images of the particular Fedora. You need to have both x86_64 and ppc64le images. Are both of them available? Then you can jump right to the next step. Otherwise, you need to submit them.

The Cloud Base image for x86_64 can be obtained on
https://alt.fedoraproject.org/cloud.  Pick the one with ``.qcow2`` extension.
The ppc64le image can be found on a page with alternative architectures
https://alt.fedoraproject.org/alt. Don't mistake PPC64LE for PPC64.
If neither that url provides the expected cloud image version (yet), there
should exist at least the "compose" version in
https://kojipkgs.fedoraproject.org/compose/cloud/, look for
`latest-Fedora-Cloud-<VERSION>/compose/Cloud/ppc64le/images` directory.

Download the image, and upload it to the `fedorainfracloud.org` OpenStack:

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


Prepare the base image
----------------------

Open a ssh connection to copr-be-dev.cloud.fedoraproject.org and edit the
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

It will most likely fail because of missing python package on the host (i.e. in the image). It needs to be there because the Ansible modules are written in python. Continue to next section to see how to solve this problem.


Creating a snapshot
-------------------

After running the ``builderpb_nova.yml`` playbook, you will get an IP address of a spawned builder. You can ssh into that builder, make changes and then create a snapshot (i.e. image) from that builder. To fix the previous issue with missing python package, run

::

    [copr@copr-be-dev ~][STG]$ ssh fedora@172.XX.XXX.XXX
    [fedora@172.XX.XXX.XXX ~]$ sudo dnf install python

Open the https://fedorainfracloud.org again and go to the ``Instances``. Make
sure that your "Current Project" is the project that you expect (``coprdev``).
There are many instances so how can you be a hundred percent sure which one you
modified? Use the IP address as an identifier.

Optionally, click on ``More -> Shut Off Instance`` for that instance (sometimes
it happens that OpenStack doesn't allow us to create snapshot from running
instance).

Click on ``More -> Create Snapshot`` for that instance.

Set snapshot name to something like ``copr-builder-x86_64-f27``. It can be a little tricky though. When you are not creating a first snapshot for the particular release, there might be an older snapshot with the same name, because the names don't have to be unique. You need to delete the older one.

In addition, make sure to make the snapshot Public, so we can use it also for production servers and Protected, so other people can't delete it.

Edit the ``builderpb_nova.yml`` playbook as you did in the :ref:`previous section <image_name>` and set the new image name. Now run the playbook again

::

    [copr@copr-be-dev ~][STG]$ ansible-playbook /home/copr/provision/builderpb_nova.yml

Iterate this process until it ends successfully.

Configure also the snapshot image to use emulated "hardware" random generator
(otherwise with our OpenStack and new guest kernels the boot would take insanely
long on gathering entropy):

::

    $ openstack image set --property hw_rng_model=virtio <THE_SNAPSHOT_UUID>


Finishing up
------------

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


Production
----------

There is a substantially less work for production instance. You just need to edit this playbook

https://infrastructure.fedoraproject.org/cgit/ansible.git/tree/roles/copr/backend/files/provision/builderpb_nova.yml

and update the `image_name` variable to the name of our new snapshot (e.g. copr-builder-x86_64-f27).
Then you need to commit the change and push it to the repository. If you don't have a write permission for it, then
ask someone who does.

Once the change is pushed, you need to re-provision the backend instance or ask someone to do it.


::

    rbac-playbook groups/copr-backend.yml -t provision_config
