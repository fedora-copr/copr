.. _dispatchers:

Action and Build dispatcher
===========================

Those two are simple systemd services (daemons) performing infinite loop of
**taking tasks** and **processing them** (see the diagram below).  They use
:ref:`worker_manager` class abstraction that has it's internal priority queue
(each task is object from ``QueueTask`` class, and provides ``task.priority``
attribute).

.. image:: /_static/dispatchers.uml.png

The important thing here is that each task needs to have unique ``task.id``
(among all other tasks).  Then, even though we read the **same** set of tasks
from frontend repeatedly, ``WorkerManager`` is able to track each task only
once.

Frontend (or the dispatcher itself) can update the task priority between
subsequent calls to ``get_frontend_tasks()``.  WorkerManager respects that, and
silently re-orders the priority queue.

Note that ``add_task()`` method filters-out the tasks which are currently
processed by any worker.
