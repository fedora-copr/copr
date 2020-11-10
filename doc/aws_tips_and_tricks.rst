.. _aws_tips_and_tricks:

AWS Tips-and-Tricks
===================

Weekly instance snapshots
-------------------------

We currently don't have automatic snapshots enabled, so you need to do them manually.

1. Please login to `Amazon AWS`_ (`us-east-1` region) and go to EC2
2. Open snapshots from the left menu
3. Filter all existing snapshots with `CoprPurpose: infrastructure`
4. See what tags they have and what is the naming convention
    - Tags: `Name`, `CoprInstance`, `CoprPurpose`, `FedoraGroup`
    - Naming: `data-copr-XY-prod-YYYY-MM-DD` where `XY` is instance name
      (`fe`, `be`, `dg`, `kg`)
    - We also keep `-last-clean` snapshots for backend and distgit instances. They are
      created from an unmounted filesystem
5. Open volumes from the left menu and filter `CoprPurpose: infrastructure`
   and `CoprInstance: production`
6. Right-click on all needed volumes and `Create Snapshot`
7. Wait, it will take an hour to create the backend snapshot.
8. Make sure that all snapshots were created correctly and from the right volumes.
   Feel free to ask for a review here.
9. Delete the previous set of snapshots (do not touch `last-clean` snapshots!)

.. _`Amazon AWS`: https://id.fedoraproject.org/saml2/SSO/Redirect?SPIdentifier=urn:amazon:webservices&RelayState=https://console.aws.amazon.com
