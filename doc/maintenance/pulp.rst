.. _pulp_maintenance:

Pulp maintenance
================

In case of any suspected Pulp-related issues, follow the Fedora Infra SOP
https://docs.fedoraproject.org/en-US/infra/sysadmin_sops/copr/#_pulp_issues


Migrate data to Pulp
--------------------

Before starting a migration, notify the user to not perform any builds or
actions while the project is being migrated. Or outright block them in
``/etc/copr/copr-be.conf`` like so::

  # Don't run any builds or actions for these owners
  blocked_owners =
      frostyx,
      praiskup

Don't forget to ``systemctl restart copr-backend.target``. Please be aware that
this doesn't stop builds and actions that were already running.

To migrate a single project from the backend storage to Pulp, run the following
command. You might want to prefix it with ``time``::

  sudo -u copr copr-change-storage --src backend --dst pulp --project frostyx/hello

To migrate all project for a specified user, run::

  sudo -u copr copr-change-storage --src backend --dst pulp --owner frostyx

The migration doesn't remove the original data. They are just not being used
anymore.


Mass migration SOP
------------------

Once, before starting the migraiton run this on the frontend::

  sudo -u copr-fe /usr/bin/copr-frontend owners-in-storage --storage backend > /tmp/owners-to-migrate.txt

and copy the file to the backend. Then copy the latest ``.json.zst`` file from
``/var/lib/copr/public_html/stats/samples/`` and run::

  cd /home/copr
  sudo -u copr copr-chunked-storage-migration \
    --owners ./owners-to-migrate.txt \
    --stats ./2026-08-19T08\:05\:43.229037+00\:00.json.zst

For every chunk:

1. Cut the first chunk out of ``copr-owner-chunks.txt`` (they are separated by
   ``---``).
2. Configure ``blocked_owners`` in ``/etc/copr/copr-be.conf``
3. Configure the same value in the Fedora Infra Ansible repository and push
4. Run ``systemctl restart copr-backend.target``
5. Run ``sudo -u copr copr-change-storage --src backend --dst pulp --blocked-owners``
6. Set banner on frontend (don't forget to update the affected owners)::
  sudo -u copr-fe /usr/bin/copr-frontend warning-banner \
    --rest "<a href='https://fedora-copr.github.io/posts/migrating-copr-results-to-pulp'>Ongoing data migration to Pulp</a> | affected owners: 000exploit - @jbangdev"
