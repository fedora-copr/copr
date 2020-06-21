Copr CLI
========

Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories. 

This part is a command line interface to use copr.


About this project:
-------------------
- Website: https://pagure.io/copr/copr
- Git: http://git.fedorahosted.org/cgit/copr.git
- Production Fedora instance: https://copr.fedorainfracloud.org/
- Development Fedora instance: http://copr-fe-dev.cloud.fedoraproject.org/


Dependencies:
-------------
.. _python-requests: http://docs.python-requests.org/en/latest/
.. _python-argparse: https://pypi.python.org/pypi/argparse

The CLI depends on:

- python (should work on 2.5, not tested)
- `python-argparse`_ (for python < 2.7)
- `python-requests`_

Usage:
------

.. _test instance: http://copr-fe-dev.cloud.fedoraproject.org/

- Create an account on copr `test instance`_
- Go to the API page: http://copr.fedoraproject.org/api
- Retrieve your API token
- Create the file ``~/.config/copr``
- In this file add the following content
(simpler way is just to copy it from /api)

::

 [copr-cli]
 username = <insert here your login>
 login = <insert here your API login>
 token = <insert here your API token>
 copr_url = https://copr.fedoraproject.org

You should be able to use copr-cli to list, create and build on copr.

.. note:: You can use directly copr-cli to list someone's copr repo but to create
 a copr or build packages into an existing repo you need to authenticate
 via the API token.
