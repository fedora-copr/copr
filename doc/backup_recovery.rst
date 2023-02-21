.. _backup_recovery:

Recovery from backups
=====================

In case of emergency ... break glass.


Backend
-------

Don't rush, take your time. It will take 5 days to sync 20TB of data so it is
not worth micro-optimizing tasks to save seconds. The ``rsync`` from
storinator is expected to run 110 MB/s while the disk can handle 130
MB/s. Our instance has 5 Gbps so the bottleneck is probably on the
network between data centers.

Prepare a new RAID array
........................

In case of a real disaster, you will probably do the recovery from
the real production instance. In case of a simulated disaster
(i.e. testing the backups), spawn a new instance::

    $ git clone git@github.com:fedora-copr/ansible-fedora-copr.git
    # Follow the README.md steps for preparation
    $ ./run-playbook pb-backup-recovery-01.yml

Once the instance is spawned, see the instance details for its public
IPv4 address, and run a second playbook::

    # The comma is needed because we don't have the IP address in our inventory
    $ ansible-playbook ./pb-backup-recovery-02.yml -i 54.81.xxx.xx, -u fedora

SSH to the instance::

    $ ssh fedora@54.81.xxx.xx
    [fedora@ip-54-81-xxx-xx ~]$ sudo su -
    [root@ip-54-81-xxx-xx ~]#

Set a root password, just in case we need to log in via EC2 Serial
Console::

    echo $RANDOM | md5sum | head -c 12; echo;
    passwd

Save the password in Bitwarden under the ``Temporary backup
instances`` vault.

Partition the disks::

    for i in /dev/nvme[1-4]n1 ; do \
        (echo gpt ; echo n ; echo ; echo ; echo ; echo ; echo w ) \
        | sudo fdisk $i; done

Create a new raid array::

    mdadm --create /dev/md0 --level raid10 \
        --name copr-backend-data --raid-disks 4 /dev/nvme[1-4]n1p1

If the raid was successfully created, a check should be running by now::

    cat /proc/mdstat

You can see the raid details using::

    mdadm --detail /dev/md0

Format and mount::

    mkfs.ext4 /dev/md0 -L copr-repo
    tune2fs -m0 /dev/md0
    mkdir /mnt/data
    chown copr:copr /mnt/data
    mount /dev/disk/by-label/copr-repo /mnt/data/


Workaround a kernel bug
.......................

There is a kernel bug causing IO operations on the RAID to get
stuck. Until it gets resolved, workaround it by::

    echo frozen > /sys/block/md0/md/sync_action

After a week or so, when all the data are copied, run::

    echo idle > /sys/block/md0/md/sync_action

to allow the RAID to finally proceed with the initial sync.



SSH key shenanigans
...................

The sync will take a couple of days so we want to run it in ``tmux``. But it
will be more useful for us to have it as root. Run ``tmux`` before switching
user::

    tmux

Switch to the ``copr`` user. This way we won't have to adjust user and
group for our data once the ``rsync`` command finishes::

    su - copr

Generate a new SSH key for this temporary instance::

    ssh-keygen -t rsa

Copy ``~/.ssh/id_rsa.pub`` into ``/home/copr/.ssh/authorized_keys`` on
storinator. You can SSH from your machine the same way you SSH to batcave::

    $ ssh frostyx@storinator01.rdu-cc.fedoraproject.org
    [frostyx@storinator01 ~][PROD]$ sudo su -
    [root@storinator01 frostyx][PROD]# su copr
    [copr@storinator01 frostyx][PROD]$ vim ~/.ssh/authorized_keys


Sync the data
.............

Sync the data. Run this command from our temporary instance, not from
storinator::

    time until rsync -av -H --info=progress2 --rsh=ssh \
        --max-alloc=4G \
        copr@storinator01.rdu-cc.fedoraproject.org:/srv/nfs/copr-be/copr-be-copr-user/backup/.sync/var/lib/copr/public_html/ \
        /mnt/data; \
        do true; done


Attach the volumes to the real instance
.......................................

Umount from the temporary instance::

    umount /mnt/data/
    mdadm --stop /dev/md0

Go through all ``copr-backend-backup-test-raid-10`` volumes in AWS EC2
and detach them from our temporary instance.

From now on, we don't care about the temporary instance.

On ``copr-backend-dev`` or ``copr-backend-prod`` run::

    systemctl stop copr-backend.target

Umount, disassemble raid, and detach volumes from ``copr-backend-dev``
or ``copr-backend-prod`` instance according to
https://docs.pagure.org/copr.copr/raid_on_backend.html#detaching-volume

Attach all the ``copr-backend-backup-test-raid-10`` volumes to the
``copr-backend-dev`` or ``copr-backend-prod`` instance. And assemble
the raid according to
https://docs.pagure.org/copr.copr/raid_on_backend.html#attaching-volume


Fix permissions
...............

At this point, we have the correct UID, GID on our data but wrong
SELinux attributes. Let's temporarily disable SELinux::

    setenforce 0

Everything should work as expected now::

    systemctl start lighttpd.service copr-backend.target

Fix SELinux attributes::

    time copr-selinux-relabel
    setenforce 1


Final steps
...........

- Delete the ``copr-backend-backup-test-raid-10`` temporary instance
- Switch all the RAID disks from ``st1`` to ``sc1``


Frontend
--------

TODO


Keygen
------

TODO


DistGit
-------

We don't have any plan for DistGit recovery
