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
