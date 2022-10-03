.. _raid_on_backend:

How to manage RAID 10 on copr-backend
=====================================

There are currently four AWS EBS sc1 volumes (4x12T, 144MB/s per volume) forming
a RAID 10 array.  On top of this is a LVM volume group named
``copr-backend-data`` (24T, and we can add more space in the future).

Everything is configured so the machine should start and mount everything
correctly.  We just can keep monitoring ``/proc/mdstat`` from time to time.


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

1. unmount: ``umount /var/lib/copr/public_html``
2. disable volume group: ``vgchange -a n copr-backend-data``
3. stop the raid: ``mdadm --stop /dev/md127``
4. now you can detach in ec2


Attaching volume
----------------

1. attach the volumes in AWS EC2
2. start raid and volume group: ``mdadm --assemble --scan``
3. mount the ``/dev/disk/by-label/copr-data`` volume

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
