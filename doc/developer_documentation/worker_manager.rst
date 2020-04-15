.. _worker_manager:

WorkerManager
=============

Method ``WorkerManager.run(timeout)`` (see diagram below) tries to process as
many tasks from queue as possible within specified timeout.  The task
heavy-lifting is done in separate independent background daemons,
one for each task (daemons follow ``BackgroundWorker class`` abstraction, see
e.g.  :ref:`backend-build-process` example).

.. image:: /_static/worker-manager-run.uml.png

Note that tasks which are not finished after one **run()** call are still
tracked in internal queue structure, and will be finished in one of the
subsequent **run()** calls.

Since the spawned workers are background (daemon) jobs, we use Redis DB for
``WorkerManager <-> BackgroundWorker`` communication; that said ``WM`` collects
the job status from the background worker.

