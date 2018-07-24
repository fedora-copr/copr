Client initialization
=====================

Before an API client can be used, it needs to be initialized with a configuration. There are several ways to do it.
The most standard option is reading the ``~/.config/copr`` file and providing it to the ``Client`` class. Please read
https://copr.fedorainfracloud.org/api/ for more information about API token.

::

    from copr.v3 import Client
    client = Client.create_from_config_file()
    pprint(client.config)

::

    {'copr_url': u'https://copr.fedorainfracloud.org',
     'login': u'secretlogin',
     'token': u'secrettoken',
     'username': u'frostyx'}

A different config file can be easily used by passing its path to ``create_from_config_file`` method.


::

    client = Client.create_from_config_file("/some/alternative/copr")

It is not required to use a configuration stored in a file though. Configuration ``dict`` can be
passed to the ``Client`` constructor.

::

    config = {'copr_url': u'https://copr.fedorainfracloud.org',
              'login': u'secretlogin',
              'token': u'secrettoken',
              'username': u'frostyx'}

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
              'username': u'frostyx'}

    build_proxy = BuildProxy(config)

And finally, it is possible to just read the configuration file.

::

    from copr.v3 import config_from_file
    config = config_from_file()
    client = Client(config)

