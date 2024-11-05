.. _backup_check:

Check that Fedora Copr Backups are OK
=====================================

This document explains how Fedora Copr backups are performed, so we can
periodically verify that everything is in place and functioning properly.  For
disaster recovery, refer to :ref:`backup_recovery`.

Copr Backend
------------

The backend storage uses a complex RAID setup to provide redundancy directly on
the server (in EC2).  Backups are then
`synchronized periodically <https://pagure.io/fedora-infra/ansible/blob/81f81668cc0ea3101cf74d56401aad3c1354f788/f/roles/rsnapshot-push/tasks/main.yml#_67>`_
to the storinator01 host as incremental backups via rsnapshot.
To verify backend backups, you should:

  1. Confirm the timestamp of the most recent backup **start**.
  2. Choose a random build that completed just before that time.
  3. Verify that this build was successfully backed up to storinator01.

Here comes more detailed guide:

1) SSH into the ``copr-be`` machine and review the ``/var/log/cron`` file.  You
   may want to check the ``crontab -l`` output first to confirm the backup
   schedule (typically Fridays though) and open an older compressed Cron log
   file::

    $ xz -d < /var/log/cron-20241101.xz | grep '(copr) CMD'
    ...
    Nov  1 03:00:02 copr-be CROND[3482216]: (copr) CMD (ionice --class=idle /usr/local/bin/rsnapshot_copr_backend >/dev/null)
    ...

   The last backup started on **November 1, 3:00 AM**.

   The backup process typically takes several days.  If there’s no corresponding
   ``CMDEND`` entry in the cron logs, it indicates that the backup is still in
   progress, and the build ID we’re trying to verify as backed up may not yet be
   included. Wait for it to complete.  Or check the previous backup increment
   instead (that means poke at ``/var/log/cron-20241025.xz``).

2) Find an appropriate build ID that finished "just before" that time above.
   For instance in the ``@copr/copr-pull-requests`` or ``@copr/copr-dev``
   projects.  Good candidate is `8185411 <https://copr.fedorainfracloud.org/coprs/g/copr/copr-pull-requests/build/8185411/>`_.

3) SSH into the `storinator01` box and locate the latest incremental backup
   (note that the sub-projects matter, ``copr-pull-requests:pr:3473`` in our
   case)::

    $ find /srv/nfs/copr-be/copr-be-copr-user/backup/.sync/var/lib/copr/public_html/results/@copr/copr-pull-requests:pr:3473 | grep 8185411 | grep rpm$
    /srv/nfs/copr-be/copr-be-copr-user/backup/.sync/var/lib/copr/public_html/results/@copr/copr-pull-requests:pr:3473/epel-8-x86_64/08185411-copr-rpmbuild/copr-builder-1.1-1.git.3.8adcc0d.el8.x86_64.rpm
    /srv/nfs/copr-be/copr-be-copr-user/backup/.sync/var/lib/copr/public_html/results/@copr/copr-pull-requests:pr:3473/epel-8-x86_64/08185411-copr-rpmbuild/copr-rpmbuild-1.1-1.git.3.8adcc0d.el8.src.rpm
    /srv/nfs/copr-be/copr-be-copr-user/backup/.sync/var/lib/copr/public_html/results/@copr/copr-pull-requests:pr:3473/epel-8-x86_64/08185411-copr-rpmbuild/copr-rpmbuild-1.1-1.git.3.8adcc0d.el8.x86_64.rpm
    /srv/nfs/copr-be/copr-be-copr-user/backup/.sync/var/lib/copr/public_html/results/@copr/copr-pull-requests:pr:3473/epel-9-x86_64/08185411-copr-rpmbuild/copr-builder-1.1-1.git.3.8adcc0d.el9.x86_64.rpm
    ...

This confirms the backups are working correctly.  While you’re on storinator,
ensure there is adequate free space on the filesystem by running
``df -h /srv/nfs/copr-be``.


Copr Frontend
-------------

For Frontend, we backup the PostgreSQL database (hourly).  Check
``/etc/cron.d/cron-backup-database-coprdb`` cron config, and the corresponding
``/backups`` directory.  That one should have the current timestamp, like::

    [root@copr-fe ~][PROD]# ls -alh /backups/
    total 662M
    drwxr-xr-x. 1 postgres root       50 Nov  5 01:21 .
    dr-xr-xr-x. 1 root     root      160 Nov 28  2023 ..
    -rw-r--r--. 1 postgres postgres 662M Nov  5 01:21 coprdb-2024-11-05.dump.xz

If we provide such an updated tarball, `rdiff-backup
<https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/rdiff-backup/>`_
periodically comes and pulls the backups "out"; as long as the box is in an
appropriate `Ansible group
<https://pagure.io/fedora-infra/ansible/blob/81f81668cc0ea3101cf74d56401aad3c1354f788/f/inventory/backups#_4>`_
and we `configure
<https://pagure.io/fedora-infra/ansible/blob/81f81668cc0ea3101cf74d56401aad3c1354f788/f/inventory/host_vars/copr-fe.aws.fedoraproject.org#_6>`_
the backup dir.

For Frontend data volume, we also do automatic volume snapshots (see Copr Keygen
info below for more info).


Copr Keygen
-----------

We don't do filesystem backups (rsync) there.  The important data —keypairs— are
stored on a separate volume ``/var/lib/copr-keygen``, and periodically
snapshotted in EC2.  Check for `the volume
<https://us-east-1.console.aws.amazon.com/ec2/home?region=us-east-1#VolumeDetails:volumeId=vol-0108e05e229bf7eaf>`_.

We do snapshots to **Ohio**, ``us-east-2``!  Volume snapshots may be filtered
with tag ``FedoraGroup=copr``.

Copr DistGit
------------

Due to Copr's design (see :ref:`architecture <architecture>`), Copr DistGit data
is extensive, measuring in terabytes, yet it’s not critical enough to require
formal backups.  We anyway at least do periodic snapshots like with Copr Keygen
above.  In the event of a complete failure, we would restore from there — or
simply initialize a new, empty volume.
