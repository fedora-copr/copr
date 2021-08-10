Run scripts
===========

Start copr backend
------------------
Script to run copr-backend ``/usr/bin/copr_be.py``
Uses backend config with default location  ``/etc/copr/copr-be.conf``.

.. TODO: use `http://sphinx-argparse.readthedocs.org/en/latest/`

Prune repository
----------------

To prune result builds use ``run/copr_prune_results.py``.
Internally it would invoke sh script ``run/copr_find_obsolete_builds.sh``

copr_prune_results.py
_____________________

Clean ups old builds. Don't affect projects with disabled ``auto_createrepo`` option.

Doesn't have startup options. Uses backend config with default location  ``/etc/copr/copr-be.conf``.
Can be changed by setting environment variable **BACKEND_CONFIG**

copr_find_obsolete_builds.sh
____________________________

Finds folders in **CHROOTPATH**, with built package which is older than **DAYS** and
there is a  higher version in a chroot repository.

copr_find_obsolete_builds.sh CHROOTPATH DAYS

VM info
-------

To get current copr-backend view on used VM use:
``run/copr_get_vm_info.py``
