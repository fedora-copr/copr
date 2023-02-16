Copr python client
==================

Copr is designed to be a lightweight buildsystem that allows contributors
to create packages, put them in repositories, and make it easy for users
to install the packages onto their system. Within the Fedora Project it
is used to allow packagers to create third party repositories.

This part is a python client to access copr service. It's aimed
to provide access to all copr api methods.

About this project:
-------------------
- Website: https://github.com/fedora-copr/copr
- Python-copr documentation: http://python-copr.readthedocs.org
- Git: https://github.com/fedora-copr/copr.git
- Test instance: http://copr.stg.fedoraproject.org/

Usage:
------

- Create an account on copr instance
- Go to the API page: http://copr.fedoraproject.org/api
- Retrieve your API login & token

::
    from copr.v3 import Client
    config = {
        "copr_url": "<url copr instance ; optional>",
        "login": "<login from /api>",
        "token": "<token from /api>",
        "username": "<copr username>",
    }
    client = Client(config)

Alternatively you could use configuration file:
- Create the file ``~/.config/copr``
- In this file add the following content
(which is also provided by /api page of the copr service)
::

 [copr-cli]
 login = <insert here your API login>
 username = <insert here your copr username>
 token = <insert here your API token>
 copr_url = <insert here copr url>
