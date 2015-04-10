Auto documentation
==================

backend.
--------
Root backend modules

.. toctree::
   package/actions
   package/job
   package/frontend
   package/constants
   package/sign
   package/createrepo
   package/helpers
   package/exceptions


backend.daemons.
----------------
Backend daemons, started by copr-be.py

.. toctree::
   package/daemons/backend
   package/daemons/dispatcher
   package/daemons/job_grab
   package/daemons/log
   package/daemons/vm_master

backend.mockremote.
-------------------
Package dedicated to executing job builds on remote VMs.

.. toctree::
   package/mockremote/__init__
   package/mockremote/builder


backend.vm_manage.
------------------
Package for VM management only.

.. toctree::
   package/vm_manage/__init__
   package/vm_manage/models
   package/vm_manage/manager
   package/vm_manage/event_handle
   package/vm_manage/executor
   package/vm_manage/spawn
   package/vm_manage/terminate
   package/vm_manage/check
