.. _api:

Copr messaging API
==================

.. autoclass:: copr_messaging.schema.BuildChrootStarted
   :members: build_id, chroot,
             package_full_name, project_full_name,
             package_epoch, package_name, package_version, package_release,
             project_owner, project_name

.. autoclass:: copr_messaging.schema.BuildChrootEnded
   :members: status, build_id, chroot,
             package_full_name, project_full_name,
             package_epoch, package_name, package_version, package_release,
             project_owner, project_name

.. [#footnote_may_be_unknown] Note that this information **may not** be known if
    the message is triggered by source build (see method :meth:`.chroot` for
    more info) -- in such case this attribute returns `None`.
