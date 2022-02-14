.. _resalloc:

Resalloc
========


.. _`terminate_resalloc_resources`:
.. _`terminate_resalloc_vms`:

Terminate resalloc resources
----------------------------

It is easier to close all resalloc tickets otherwise there will be dangling VMs
preventing the backend from starting new ones.

Edit the ``/etc/resallocserver/pools.yaml`` file and in all section, set::

    max: 0

Then delete all current resources::

    su - resalloc
    resalloc-maint resource-delete --all
