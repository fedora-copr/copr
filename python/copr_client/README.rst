Copr python client
========

Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a python client to access copr service.

About this project:
-------------------
- Webiste:  https://fedorahosted.org/copr/
- Git: http://git.fedorahosted.org/cgit/copr.git
- Test instance: http://copr-fe.cloud.fedoraproject.org/

Dependencies:
-------------
The client depends on:

.. _python2.6 +
.. _python-requests: http://docs.python-requests.org/en/latest/

Usage:
------

- Create an account on copr `test instance`_
- Go to the API page: http://copr-fe.cloud.fedoraproject.org/api
- Retrieve your API token

::

    from python_copr.main import CoprClient


Alternatively you could use configuration file:
- Create the file ``~/.config/copr``
- In this file add the following content
(which is also provided by /api page of the copr service)
::

 [copr-cli]
 username = <insert here your API login>
 token = <insert here your API token>


You should then be able to use copr-cli to list, create and build on copr.
