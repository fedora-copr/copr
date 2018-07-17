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

Copr currently supports three independent API versions.

.. toctree::
    :maxdepth: 1

    ClientV1.rst
    ClientV2.rst
    ClientV3.rst

Both Legacy client and Client version 2 are now obsoleted, please migrate to Client version 3.

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`


.. _APIv2: http://copr-rest-api.readthedocs.org/en/latest/index.html
