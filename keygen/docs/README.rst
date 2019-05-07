An outline of package sign process in Copr
==========================================

To sign packages we decided to use obs-signd
`1 <http://en.opensuse.org/openSUSE:Build_Service_Signer>`__.
Unfortunately it doesn't manage user keys in any way, but it's possible
to minimize Copr operations with gpg key-pairs.

Expected setup
--------------

**host-sign**: secure machine where key-pairs is stored in /usr/share/copr-keygen/gnupg/
it runs:

-  [A] perl signd from *obs-signd*
-  [B] copr-keygen service

**host-build**: backend where builds occurs and result rpms are signed
by invocation of /bin/sign [C] from *obs-signd*

[C] is configured by /etc/sign.conf to access [A] at host-0

When user ``foo`` builds first package, service [B] will be invoked to generate
new keys (they will be contained in the keyring in
**GPGHOMEDIR**). Also it creates dummy file into **PHRASESDIR**,
that file indicates that user ``foo`` exists for [A].
Finally [A] can sign packages for user ``foo`` without receiving keys
through network.

**copr-backend** do everything related to sign through new module
**backend.sign** which either runs [C] or calls [B].

Configuration notes
-------------------

At **host-build**
+++++++++++++++++

| sign should be executed from the root user
| **/etc/sign.conf**:

-  server: host of machine with signd

ensure that configs/sudoers/copr\_signer is copied into /etc/sudoers.d/

At **host-sign**
++++++++++++++++

**/etc/sign.conf**:
 - allow: list of backend hosts
 - phrases: /var/lib/copr-keygen/phrases -- location of **PHRASESDIR**


**NB:**
 obs-signd always run as root and doesn't accept alternative
 **GPGHOMEDIR**. To overcome this obstacle we added ``/usr/bin/gpg_copr.sh``
 Bash script wrapper which calls ``gpg2`` with correct user and homedir
