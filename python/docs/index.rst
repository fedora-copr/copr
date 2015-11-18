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

.. toctree::
    :maxdepth: 1

    installation.rst

Contact
=======

If you have any questions, please contact us:

    - IRC: #fedora-buildsys@irc.freenode.net
    - mailing list: copr-devel@lists.fedorahosted.org
      [`signup <https://fedorahosted.org/mailman/listinfo/copr-devel>`_]
      [`archives <https://lists.fedorahosted.org/pipermail/copr-devel/>`_]


Usage
=====

Recently Copr started to offer an alternative REST-like APIv2_.
New API is provided by mostly independent `client_v2` package.

.. toctree::
    :maxdepth: 1

    ClientV1.rst
    ClientV2.rst


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _APIv2: http://copr-rest-api.readthedocs.org/en/latest/index.html
