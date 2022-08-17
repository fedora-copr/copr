Client initialization
=====================

Before an API client can be used, it needs to be initialized with a
configuration.  There are several ways to do it.  The most standard option is
reading the ``~/.config/copr`` file and providing it to the ``Client`` class.

Such a configuration file typically has::

    [copr-cli]
    copr_url = https://copr.fedorainfracloud.org
    username = coprusername
    login = secretlogin
    token = secrettoken
    # expiration date: 2023-01-17

To get your configuration file for the Fedora Copr instance, go to
https://copr.fedorainfracloud.org/api/

The only mandatory field though is ``copr_url``::

    [copr-cli]
    copr_url = https://copr.fedorainfracloud.org

With such a simplified configuration, you can still do the read-only API
queries that do not require user-authentication (listing projects, builds,
etc.).

Alternatively, the Copr server you work with might support GSSAPI
authentication (Fedora Copr does).  To let the Client use your ``kinit``
tokens, you need to enable GSSAPI authentication first::

    [copr-cli]
    copr_url = https://copr.fedorainfracloud.org
    gssapi = true

Having the config file prepared, you can finally use it for creating a
``Client`` instance.  Just like::

    from copr.v3 import Client
    from pprint import pprint
    client = Client.create_from_config_file()
    pprint(client.config)

::

    {'copr_url': u'https://copr.fedorainfracloud.org',
     'login': u'secretlogin',
     'token': u'secrettoken',
     'username': u'coprusername'}

A different config file can be easily used by passing its path to ``create_from_config_file`` method.


::

    client = Client.create_from_config_file("/some/alternative/copr")

It is not required to use a configuration stored in a file though. Configuration ``dict`` can be
passed to the ``Client`` constructor.

::

    config = {'copr_url': u'https://copr.fedorainfracloud.org',
              'login': u'secretlogin',
              'token': u'secrettoken',
              'username': u'coprusername'}

    client = Client(config)
    assert client.config == config

Similarly it can be done when using proxies directly.

::

    from copr.v3 import BuildProxy
    build_proxy = BuildProxy.create_from_config_file()

Or even without configuration file.

::

    config = {'copr_url': u'https://copr.fedorainfracloud.org',
              'login': u'secretlogin',
              'token': u'secrettoken',
              'username': u'coprusername'}

    build_proxy = BuildProxy(config)

And finally, it is possible to just read the configuration file.

::

    from copr.v3 import config_from_file
    config = config_from_file()
    client = Client(config)

