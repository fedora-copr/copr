.. _consuming:

How to consume Copr messages
============================

Listening on fedora-messaging bus
---------------------------------

.. todo:: 

    For the simplest example, we should only say this:

        $ fedora-messaging \
            --conf /etc/fedora-messaging/fedora.toml \
            consume --routing-key '#.copr.#'

    The default behavior of python-fedora-messaging is that - if
    copr-messaging package is installed - the messages are automatically retyped
    to proper message class objects according to theirs topics.  But so far we
    send messages to fedmsg -> that is proxied to fedora-messaging -> and such
    proxied messages don't contain enough info for this to happen.

`Fedora Copr instance`_ sends messages to fedora-messaging AMQP bus, which makes
the messages available to general public.  The simplest way to consume Copr
messages from command-line is::

    $ fedora-messaging \
            --conf /etc/fedora-messaging/fedora.toml \
            consume --routing-key '#.copr.#' \
            --callback copr_messaging.fedora:Printer \
    build_chroot_started(): Copr Message in project "loveshack/livhpc": build 958843: chroot "fedora-29-x86_64" started.
    build_chroot_started(): Copr Message in project "loveshack/livhpc": build 958843: chroot "fedora-30-x86_64" started.
    build_chroot_started(): Copr Message in project "loveshack/livhpc": build 958843: chroot "fedora-29-ppc64le" started.
    build_chroot_ended(): Copr Message in project "decathorpe/xmlunit-pr": build 958393: chroot "fedora-rawhide-x86_64" ended as "failed".
    build_chroot_started(): Copr Message in project "decathorpe/xmlunit-pr": build 958381: chroot "fedora-rawhide-x86_64" started.

One can make more customized consumer class by inheriting from the abstract
Consumer class::

    $ cat consumer.py
    from copr_messaging import fedora
    class Consumer(fedora.Consumer):
        def build_chroot_ended(self, message):
            print(message) # or anything else with BuildChrootEnded object!
        def build_chroot_started(self, message):
            print(message) # BuildChrootStarted object
    $ PYTHONPATH=`pwd` fedora-messaging \
        --conf /etc/fedora-messaging/fedora.toml \
        consume --callback consumer:Consumer --routing-key '#.copr.#'

See :class:`copr_messaging.schema.BuildChrootStarted` and
:class:`copr_messaging.schema.BuildChrootEnded` for more info about the message
API.


Listening on STOMP bus
----------------------

This part doesn't apply to `Fedora Copr instance`_, so check that your instance
publishes on `STOMP bus`_ first.

Similarly to :class:`copr_messaging.fedora.Consumer`, there's
:class:`copr_messaging.stomp.Consumer` class having the same user API (share the
base class)::

    $ cat consumer.py
    #! /usr/bin/python3

    import stomp
    from copr_messaging.stomp import Consumer

    class Listener(Consumer):
        def build_chroot_ended(self, message):
            # message is of BuildChrootStarted type
            print(message) # or do anything else!

    c = stomp.Connection(...)
    c.set_listener('', Consumer())
    c.set_ssl(...)
    c.start()
    c.connect(wait=True)
    # check where your copr publishes
    c.subscribe('/queue/Consumer.copr.*.VirtualTopic.devel.copr.build.*', 3)
    c.disconnect()


.. _`Fedora Copr instance`: https://copr.fedorainfracloud.org/
.. _`STOMP bus`: https://stomp.github.io/
