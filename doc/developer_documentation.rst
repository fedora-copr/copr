.. _developer_documentation:

Developer Documentation
=======================

This section contains information about developer topics. You may also be interested in :ref:`user_documentation` and :ref:`downloads`.

Source
------

Copr comes in several pieces. You can browse the source here:

* The source for Copr itself: https://pagure.io/copr/copr

Working with the code
---------------------

* :ref:`how_to_install` How to Install - Copr is intended as service. You most likely do not want to set up your own instance. But if you really want to, Copr set up is documented here.

* :ref:`contribute` How to Contribute - Do you want to help us? Start here.

* :ref:`git_guide` Git Guide -- how to work with Git, the source control of choice for Copr

* :ref:`patch_process` -- how to go about creating a new patch and submitting it to the mailing list

* :ref:`building_package` -- how to build Copr itself

* `Database schema <http://miroslav.suchy.cz/copr/coprdb/>`_

* `Documentation of python code <http://miroslav.suchy.cz/copr/python-doc/>`_ - most up-to-date documentation are in copr-frontend-doc and copr-backend-doc packages.

History
-------

* `Origins <http://fedoraproject.org/wiki/Meetings:Kopers_IRC_log_20100324.2>`_

Misc
----

* :ref:`brainstorming`

* :ref:`rawhide_to_release`

* :ref:`seeddb`

SRPM URL/Upload build schema
----------------------------

Here is an example of how building process goes (for the simplest case of SRPM build) in COPR:

.. image:: _static/srpm-build.jpeg

Note that we need to figure out whether CoprDistGit is actually still needed in the COPR architecture. That's why the lines are dotted there. It is still present in the current architecture though.
