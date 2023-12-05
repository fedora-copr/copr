.. _raid_on_backend:

How to manage RAID 10 on copr-backend
=====================================

There are currently six AWS EBS sc1 volumes used for hosting Copr Backend build
results. Four disks are forming one 24T ``raid10``, two more disk form 16T
``raid1``.  These two arrays are used as "physical volumes" for the
``copr-backend-data`` LVM volume group, and we have a single logical volume on
it with the same name ``copr-backend-data`` (``ext4`` formatted, mounted as
``/var/lib/copr/public_html``).

Everything is configured so the machine starts on its own and mounts everything
correctly.  We just need to take a look at ``/proc/mdstat`` from time to time.

Manually checking/stopping checks
---------------------------------

Commands needed::

    echo idle > /sys/block/md127/md/sync_action
    echo check > /sys/block/md127/md/sync_action


Detaching volume
----------------

It's not safe to just force detach the volume in AWS EC2, it could cause data
corruption.  Since there are several layers (volumes -> raid -> LVM -> ext4) we
need to go the vice versa while detaching.

1. stop apache, copr-backend, cron jobs, etc.
2. unmount: ``umount /var/lib/copr/public_html``
3. disable volume group: ``vgchange -a n copr-backend-data``
4. stop raids: ``mdadm --stop /dev/md127``
5. now you can detach the volumes from the instance in ec2


Attaching volume
----------------

1. attach the volumes in AWS EC2
2. start raid and volume group ``mdadm --assemble --scan``.  In case the
   ``--assemble --scan`` doesn't reconstruct the array, it is OK to add the
   volumes manually ``mdadm /dev/md127 --add /dev/nvme2n1p1``.
3. mount the ``/dev/disk/by-label/copr-repo`` volume

There's a `ansible configuration`_ for this, and `list of volumes`_.


Adding more space
-----------------

1. Create two ``gp3`` volumes in EC2 of the same size and type, tag them with
   ``FedoraGroup: copr``, ``CoprInstance: production``, ``CoprPurpose:
   infrastructure``.  Attach them to a freshly started temporary instance (we
   don't want to overload I/O with the `initial RAID sync <mdadm_sync_>`_ on
   production backend).  Make sure the instance type has enough EBS throughput
   to perform the initial sync quickly enough.

2. Always partition the disks with a single partition on them, otherwise kernel
   might have troubles to auto-assemble the disk arrays::

        cfdisk /dev/nvmeXn1
        cfdisk /dev/nvmeYn1

3. Create the ``raid1`` array on both the new **partitions**::

        $ mdadm --create --name=raid-be-03 --verbose /dev/mdXYZ --level=1 --raid-devices=2 /dev/nvmeXn1p1 /dev/nvmeYn1p1

   Wait till the new empty `array is synchronized <mdadm_sync_>`_ (may take hours
   or days, note we sync 2x16T).  Check the details with ``mdadm -Db
   /dev/md/raid-be-03``.  See the tips bellow how to make the sync speed
   unlimited with ``sysctl``.

   .. note::

        In case the disk is marked "readonly", you might need
        the ``mdadm --readwrite /dev/md/raid-be-03`` command.

4. Place the new ``raid1`` array into the volume group as a new physical
   volume (vgextend does pvcreate automatically)::

    $ vgextend copr-backend-data /dev/md/raid-be-03

5. Extend the logical volume to span all the free space::

    $ lvextend -l +100%FREE /dev/copr-backend-data/copr-backend-data

6. Resize the underlying ``ext4`` filesystem (takes 15 minutes and more!)::

    $ resize2fs /dev/copr-backend-data/copr-backend-data

7. Switch the volume types from ``gp3`` to ``sc1``, we don't need the power of
   ``gp3`` for backend purposes.

8. Modify the https://github.com/fedora-copr/ansible-fedora-copr group vars
   referencing the set(s) of volume IDs.


Other tips
----------

Note the **sysctl** ``dev.raid.speed_limit_max`` (in KB/s), this might affect
(limit) the initial sync speed, periodic raid checks and potentially the raid
re-build.

While trying to do a fast rsync, we experimented with a very large instance type
(c5d.18xlarge, 144GB RAM) and with `vm.vfs_cache_pressure=2`, to keep as many
inodes and dentries in kernel caches (see ``slabtop``, we eventually had 60M of
inodes cached, 28M inodes and 15T synced in 6.5hours).   We had also decreased
the ``dirty_ratio`` and ``dirty_background_ratio`` to have more frequent syncs
considering the large RAM.

.. _`ansible configuration`: https://pagure.io/fedora-infra/ansible/blob/main/f/roles/copr/backend/tasks/mount_fs.yml
.. _`list of volumes`: https://pagure.io/fedora-infra/ansible/blob/main/f/inventory/group_vars/copr_all_instances_aws
.. _mdadm_sync: https://raid.wiki.kernel.org/index.php/Initial_Array_Creation
