.. _enlarge_disk_copr_be:

How to enlarge disk on copr-be
==============================

1. Login to Amazon AWS [amazon-aws] (`us-east-1` region) and go to EC2
2. Open volumes from the left menu
3. Filter `copr-be-prod`
4. In case something goes wrong, create a snapshot with the same tags the volume already has
   (see instructions in AWS Tips-and-Tricks).
   Name it so that the snapshot can then be distinguished from the others,
   because after enlarging the disk it will be deleted. Note that creating the snapshot can take about
   one hour.
5. After creating a snapshot, right-click on `copr-be-prod` and click on `Modify Volume`
6. In the size field, write how big you want the volume to be
7. After the enlargement is done (this may take several hours if we speak about TB)
8. Run::

    [comment]: # (nvme reset /dev/nvme1 - we don't have to do this anymore)
    growpart /dev/nvme1n1 1
    resize2fs /dev/nvme1n1p1

9. Delete the snapshot from step 4


[amazon-aws]: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
