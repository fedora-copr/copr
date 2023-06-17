.. _enlarge_volumes:

How to enlarge disk partitions
==============================

This document describes how to enlarge Fedora Copr infrastructure volumes hosted
in AWS.


How to enlarge btrfs non-data partitions
----------------------------------------

At some point, Fedora Cloud images moved to btrfs and we inherited those.  From
time to time we need to enlarge `/` partition, or alike.  We don't do
"snapshots" in this part becase we don't treat the critical (data) volumes.

1. `Login to AWS`_, find the volume in question, and enlarge accordingly
2. SSH to the corresponding machine, and run something like::

    [root@copr-fe copr-frontend][PROD]# growpart /dev/nvme0n1 5
    CHANGED: partition=5 start=2265088 old: size=102592479 end=104857567 new: size=144535519 end=146800607

    [root@copr-fe copr-frontend][PROD]# btrfs filesystem resize max /
    Resize device id 1 (/dev/nvme0n1p5) from 48.92GiB to max


How to enlarge other partititions
---------------------------------

1. `Login to AWS`_, find the volume in question
2. In case something goes wrong, you may create a snapshot with the same tags
   the volume already has (see instructions in AWS Tips-and-Tricks).  Name it so
   that the snapshot can then be distinguished from the others, because after
   enlarging the disk it will be deleted. Note that creating the snapshot can
   take quite some time.
3. Enlarge the volume accordingly (may take hours, if we speak about TBs)
4. SSH to the VM, and run something like::

    $ nvme reset /dev/nvme1  # NOTE! we don't have to do this anymore, check lsblk
    $ growpart /dev/nvme1n1 1
    $ resize2fs /dev/nvme1n1p1

5. Delete the snapshot from step 2, if any.

.. _`Login to AWS`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
