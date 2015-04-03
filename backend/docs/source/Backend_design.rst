Backend design
==============

Backend consists of the multiple process and a few utility scripts.

The main process :py:class:`~backend.daemons.backend.CoprBackend` is started by ``/usr/bin/copr_be.py`` script.
Default backend configuration is stored in ``/etc/copr/copr-be.conf``. Running **redis** server are required.

**CoprBackend** process starts the following components at the init:
    - Centralised logging: :py:class:`~backend.daemons.log.RedisLogHandler` listens for the redis pubsub for log events
    - :py:class:`~backend.daemons.job_grab.CoprJobGrab` polling pending builds and actions from the copr frontend.
        Builds are routed to the appropriate task queue and action are executed by **CoprJobGrab** itself.
    - VM management is controlled by :py:class:`~backend.daemons.vm_master.VmMaster`.
        See :ref:VmManagement: for details about Vm handling.

After spawning aux processes **CoprBackend** dynamically spawns and terminates worker processes :py:class:`~backend.daemons.dispatcher.Worker`.

Communication with frontend
---------------------------

Action processing
-----------------

Build lifecycle
---------------

