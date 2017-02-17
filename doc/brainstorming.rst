.. _brainstorming:

Brainbox
========

This is just a page to collect brainwaves/ideas/evil-thoughts for Copr. 

Frontend
--------

* make link to /api page (Done)
* Extend APIs
* localize frontend (use Transifex)
* Meet Docstring standards for the code.
* Allow a repo author to optionally provide a url to the upstream source repo (visible to viewers)
* Allow a repo author to optionally provide a url to the spec file (visible to viewers)

Backend
-------

* change instance type by build request for more mem/procs/extend timeouts
   - use extra-vars?
   - need ansible 0.9?
* auto-timer/cleanup script for old instances that may have been orphaned
* prune out builders when we drop the number of them active
* LOADS of fixme and catching weird conditions
* make logging from mockremote more sane and consistent
* mock configs should be pushed to instances at creation time
   - single url to repos, not mirrorlists
* consider making each worker return job to a completed queue so the primary
  process can do other kinds of notification
* email notifications from backend?
* work on a way to find and cancel a specific build that's happening other than just killing the instance
* determine if it is properly checking the timeout from a dead instance
* maybe dump out the PID of the worker that is running so we know which one to kill?

Command line interface
----------------------

* integrate with fedpkg

Other
-----

* Create CoprReleaser for `Tito <https://github.com/dgoodwin/tito>`_ (Done)
* provide .repo file (not sure if backend or frontend). (Done)
* Logo. We desperatly :) need logo. I was thinking about simplified picture of [http://en.wikipedia.org/wiki/Dill Dill] which is pronaunced in Czech (my native language) exactly same as Copr.
