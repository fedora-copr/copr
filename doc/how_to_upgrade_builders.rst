.. _how_to_upgrade_builders:

How to upgrade builders
=======================

This article explains how to upgrade the Copr builders in OpenStack to a newer Fedora once it is released.

Keep amending this page if you find something not matching reality or expectations.


Requirements
------------

* ssh access to copr-be-dev.cloud.fedoraproject.org
* an account on https://fedorainfracloud.org.


Provide the image
-----------------

The first thing you need to figure out is what image should you use and where to get it. Luckily there is an image registry on https://fedorainfracloud.org/dashboard/project/images/. By default you see only the project images, to see all of them, click on the ``Public`` button.

Search for the ``Fedora-Cloud-Base-*`` images of the particular Fedora. You need to have both x86_64 and ppc64le images. Are both of them available? Then you can jump right to the next step. Otherwise, you need to submit them.

The Cloud Base image for x86_64 can be obtained on https://alt.fedoraproject.org/cloud. Pick the one with ``.qcow2`` extension. The ppc64le image can be found on a page with alternative architectures https://alt.fedoraproject.org/alt. Don't mistake PPC64LE for PPC64.

Then click to ``Create Image`` in the registry and fill the fields like this

* Name - Use the filename
* Image Location - Provide the full URL to the image
* Format - QCOW2
* Architecture - x86_64 or ppc64le
* Public - Yes, so other people can use it too
* Protected - Yes, so other people can't delete it

Once it is done, you need to edit this playbook

https://infrastructure.fedoraproject.org/cgit/ansible.git/tree/playbooks/hosts/fed-cloud09.cloud.fedoraproject.org.yml

and add info about the image(s) that you have uploaded. See the task called ``- name: Add the images``. If you don't have a push access, send a patch to someone who has.


Prepare the base image
----------------------

Open a ssh connection to copr-be-dev.cloud.fedoraproject.org and edit the ``/home/copr/provision/builderpb_nova.yml`` playbook. There is the following part

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

Also install ``libselinux-python`` package, which is needed as well.

::

    [fedora@172.XX.XXX.XXX ~]$ sudo dnf install libselinux-python

Open the https://fedorainfracloud.org again and go to the ``Instances``. Make sure that your "Current Project" is the project that you expect (``coprdev``). There are many instances so how can you be a hundred percent sure which one you modified? Use the IP address as an identifier. Click on ``Create Snapshot`` for that instance.

Set snapshot name to something like ``copr-builder-x86_64-f27``. It can be a little tricky though. When you are not creating a first snapshot for the particular release, there might be an older snapshot with the same name, because the names don't have to be unique. You need to delete the older one.

Edit the ``builderpb_nova.yml`` playbook as you did in the :ref:`previous section <image_name>` and set the new image name. Now run the playbook again

::

    [copr@copr-be-dev ~][STG]$ ansible-playbook /home/copr/provision/builderpb_nova.yml

Iterate this process until it ends successfully.


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
