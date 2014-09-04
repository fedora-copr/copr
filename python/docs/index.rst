.. python-copr documentation master file, created by
   sphinx-quickstart on Thu Sep  4 16:44:28 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

About
=====

Python-copr is a python client to access the Copr build service
through its `API <http://copr.fedoraproject.org/api>`_.

Python-copr right now in an alpha stage, so expect lot of changes.

Installation
============

repo
++++
[Soon] Available for fedora 19, fedora 20.
dnf install python-copr python-copr-doc

source
++++++

``git clone https://git.fedorahosted.org/git/copr.git``



Usage
=====

All interaction are done through copr.CoprClient.

It can be created directly or using config file :file:`/etc/copr.conf`

*CoprClient* has methods directly reflects Copr api, received data
 are wrapped into the Response object.


Auto-generated documentation
----------------------------
See method signatures and response objects in
the auto generated documentation:


.. toctree::

    CoprClient
    Responses


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
