Prune repository
================

To prune result builds use ``run/copr_prune_results.py``.
Internally it would invoke sh script ``run/copr_prune_old_builds.sh``

copr_prune_results.py
---------------------
Clean ups old builds. Don't affect projects with disabled ``auto_creatrepo`` option.


Doesn't have startup options. Uses backend config with default location  ``/etc/copr/copr-be.conf``.
Can be changed by setting environment variable **BACKEND_CONFIG**

copr_prune_old_builds.sh
------------------------


copr_prune_old_builds.sh REPOPATH DAYS
