.. python-copr documentation master file, created by
   sphinx-quickstart on Thu Sep  4 16:44:28 2014.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

About
=====

Python-copr is a python client to access the Copr build service
through its `API <http://copr.fedoraproject.org/api>`_.

Python-copr right now is in alpha stage, so expect lot of changes. Now it targets python 2.6+
and python3.3+.


Installation
============

Dependencies:
-------------
::

 python2.6+
 python-requests
 python-six

repo
----
[Soon] Available for fedora 19, fedora 20.
::

    dnf install python-copr python-copr-doc

source
------

.. code-block:: bash

    git clone https://git.fedorahosted.org/git/copr.git
    cd python
    # enable virtualenv if needed
    pip install -r requirements.txt
    python setup.py install

Contact
=======

If you have any questions, please contact us:

    - IRC: #fedora-buildsys@irc.freenode.net
    - mailing list: copr-devel@lists.fedorahosted.org
      [`signup <https://fedorahosted.org/mailman/listinfo/copr-devel>`_]
      [`archives <https://lists.fedorahosted.org/pipermail/copr-devel/>`_]


Usage
=====

All interaction are done through copr.CoprClient.
It can be created directly or using config file :file:`/etc/copr.conf`

*CoprClient* offers methods that directly reflect Copr api. Received data
are wrapped into the Response object.
Depending on used methods Responses will have different set of
provided attributes and methods.


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
