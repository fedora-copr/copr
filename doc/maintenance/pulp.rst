.. _pulp_maintenance:

Pulp maintenance
================

In case of any suspected Pulp-related issues, follow the Fedora Infra SOP
https://docs.fedoraproject.org/en-US/infra/sysadmin_guide/copr/#_pulp_issues


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
