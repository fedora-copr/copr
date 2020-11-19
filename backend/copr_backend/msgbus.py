"""
Message buses abstraction.
"""

import os
import logging
import copy
import json

from copr_messaging import schema

from .constants import BuildStatus

try:
    import fedmsg
except ImportError:
    # fedmsg is optional
    fedmsg = None

try:
    import stomp
    from stomp import ConnectionListener as StompConnectionListener
except ImportError:
    # stomp is also optional
    stomp = None
    StompConnectionListener = object


def message_from_worker_job(style, topic, job, who, ip, pid):
    """
    Compat wrapper generating message object for messages defined before we
    switched to fedora-messaging jsonschema-aware model.  This can be removed
    once we can exepect that people are using copr-messaging module (and thus
    we can change message format without affecting the API).
    """
    if style == 'v1':
        content = {
            'user': job.submitter,
            'copr': job.project_name,
            'owner': job.project_owner,
            'pkg': job.package_name,
            'build': job.build_id,
            'chroot': job.chroot,
            'version': job.package_version,
            'status': job.status,
        }
        content.update({'ip': ip, 'who': who, 'pid': pid})

        message_types = {
            'build.start': {
                'what': "build start: user:{user} copr:{copr}" \
                        " pkg:{pkg} build:{build} ip:{ip} pid:{pid}",
                'class': schema.BuildChrootStartedV1,
            },
            'chroot.start': {
                'what': "chroot start: chroot:{chroot} user:{user}" \
                        " copr:{copr} pkg:{pkg} build:{build} ip:{ip} pid:{pid}",
                'class': schema.BuildChrootStartedV1DontUse,
            },
            'build.end': {
                'what': "build end: user:{user} copr:{copr} build:{build}" \
                        " pkg:{pkg} version:{version} ip:{ip} pid:{pid} status:{status}",
                'class': schema.BuildChrootEndedV1,
            },
        }

        content['what'] = message_types[topic]['what'].format(**content)
        message = message_types[topic]['class'](body=content)
        return message

    elif style == 'v1stomp':
        und = '(undefined)'
        content = {
            'user':        getattr(job, 'submitter', und),
            'copr':        getattr(job, 'project_name', und),
            'owner':       getattr(job, 'project_owner', und),
            'pkg':         getattr(job, 'package_name', und),
            'build':       getattr(job, 'build_id', und),
            'chroot':      getattr(job, 'chroot', und),
            'version':     getattr(job, 'package_version', und),
            'status':      getattr(job, 'status', und),
        }

        content['str_status'] = BuildStatus.string(content['status'])
        content.update({'ip': ip, 'who': who, 'pid': pid})

        msg_format = {
            'build.start': {
                'keys': {
                    'build': '{build}',
                    'owner': '{owner}',
                    'copr': '{copr}',
                    'submitter': '{user}',
                    'package': '{pkg}-{version}',
                    'chroot': '{chroot}',
                    'builder': '{ip}',
                    'status': '{str_status}',
                    'status_int': '{status}',
                },
                'class': schema.BuildChrootStartedV1Stomp,
            },
            'build.end': {
                'keys': {
                    'build': '{build}',
                    'owner': '{owner}',
                    'copr': '{copr}',
                    'submitter': '{user}',
                    'package': '{pkg}-{version}',
                    'chroot': '{chroot}',
                    'builder': '{ip}',
                    'status': '{str_status}',
                    'status_int': '{status}',
                },
                'class': schema.BuildChrootEndedV1Stomp,
            },
            'chroot.start': {
                'keys': {
                    'chroot': "{chroot}",
                },
                'class': schema.BuildChrootStartedV1StompDontUse,
            },
        }

        body = {}
        for key in msg_format[topic]['keys']:
            body[key] = msg_format[topic]['keys'][key].format(**content)

        return msg_format[topic]['class'](body=body)

    raise NotImplementedError


class MsgBus(object):
    """
    An "abstract" message bus class, don't instantiate!
    """
    messages = {}
    style = 'v1'
    bus_type = "msgbus"

    def __init__(self, opts, log=None):
        self.opts = opts
        # Fix bus_id soon enough.
        self.opts.bus_id = getattr(self.opts, 'bus_id', type(self).__name__)

        self.opts.bus_publish_retries = getattr(self.opts, 'bus_publish_retries', 5)

        self.log = log
        if not log:
            self.log = logging
            logging.basicConfig(level=logging.DEBUG)

        self.log.info("initializing bus")
        if hasattr(self.opts, 'messages'):
            self.messages.update(self.opts.messages)

    def _send_message(self, message):
        """
        Send message from fedora_messaging.message.Message (or subclass) object.
        The object is already validated.
        """
        raise NotImplementedError

    def send_message(self, message):
        """
        Validate and send message from fedora_messaging.message.Message (or
        subclass) object.
        """
        try:
            message.validate()
        except Exception: # pylint: disable=W0703
            self.log.exception("Failed to validate a message")
            return

        for attempt in range(1, self.opts.bus_publish_retries + 1):
            try:
                self._send_message(message)
                break
            except Exception: # pylint: disable=W0703
                # We don't want to halt the worker because of messaging.
                self.log.exception("Attempt %s to publish a message failed", attempt)

    def announce_job(self, msg_type, job, who, ip, pid):
        """
        Compat thing to be removed;  future types of messages (v2+) should be
        constructed at caller side, not in this class.
        """
        msg = message_from_worker_job(self.style, msg_type, job, who, ip, pid)
        self.send_message(msg)

    @property
    def info(self):
        """ string info about the bus """
        return "{} bus".format(self.bus_type)


class StompListener(StompConnectionListener):
    def __init__(self, msgbus):
        self.msgbus = msgbus

    def on_error(self, headers, message):
        self.msgbus.log.warning('received an error "%s"' % message)

    def on_disconnected(self):
        self.msgbus.log.warning('disconnected, trying to connect again..')
        self.msgbus.connect()


class MsgBusStomp(MsgBus):
    """
    Connect to STOMP bus and send messages.  Make sure you have correctly
    configured 'messages' attribute in every message bus configuration, no
    default messages here!
    """

    style = 'v1stomp'
    bus_type = "stomp"

    def connect(self):
        """
        connect (even repeatedly) to STOMP message bus
        """
        self.log.debug("connecting")
        self.conn.connect(
            # username/passcode can be None if ssl_key is used
            username=self.username,
            passcode=self.password,
            wait=True,
        )
        if not getattr(self.opts, 'destination', None):
            setattr(self.opts, 'destination', '/default')


    def __init__(self, opts, log=None):
        super(MsgBusStomp, self).__init__(opts, log)

        hosts = []
        # shortcuts
        if getattr(self.opts, 'hosts', None):
            assert type(self.opts.hosts) == list
            hosts += self.opts.hosts

        if getattr(self.opts, 'host', None):
            # TODO: Compat to be removed.
            self.log.warning("obsoleted 'host' parameter, use 'hosts' " \
                             "array (failover capable)")
            hosts.append((self.opts.host, self.opts.port))

        # Ensure integer ports.
        hosts = [(pair[0], int(pair[1])) for pair in hosts]

        self.conn = stomp.Connection(hosts)
        self.conn.set_listener('', StompListener(self))

        # allow dict.get() (with default None) method
        auth = {}
        if getattr(self.opts, 'auth', None):
            auth = self.opts.auth

        self.username = auth.get('username')
        self.password = auth.get('password')
        ssl_key  = auth.get('key_file')
        ssl_crt  = auth.get('cert_file')
        cacert = getattr(self.opts, 'cacert', None)

        if (ssl_key, ssl_crt, cacert) != (None, None, None):
            self.log.debug("ssl: key = {0}, crt = {1}, cacert = {2}".format(
                ssl_key, ssl_crt, cacert))

            self.conn.set_ssl(
                for_hosts=hosts,
                key_file=ssl_key,
                cert_file=ssl_crt,
                ca_certs=cacert
            )

        self.connect()


    def _send_message(self, message):
        topic = message.topic
        body = message.body
        send_headers = {}
        send_headers['topic'] = topic

        destination = '{0}.{1}'.format(self.opts.destination, topic)

        # backward compat (before we mistakenly sent everything to the same
        # destination), drop once every consumer moved to copr-messaging module
        # and thus we can expect them to consume fixed messages too.
        if self.style == 'v1stomp':
            destination = self.opts.destination

        self.conn.send(body=json.dumps(body), headers=send_headers,
                       destination=destination,
                       content_type='application/json')


class MsgBusFedmsg(MsgBus):
    """
    Connect to fedmsg and send messages over it.
    """

    bus_type = "fedmsg"

    def __init__(self, log=None):
        # Hack to not require opts argument for now.
        opts = type('', (), {})
        opts.headers = {}

        super(MsgBusFedmsg, self).__init__(opts, log)

        fedmsg.init(name='relay_inbound', cert_prefix='copr', active=True)

    def _send_message(self, message):
        fedmsg.publish(modname='copr', topic=message.topic, msg=message.body)


class MsgBusFedoraMessaging(MsgBus):
    """
    Connect to fedora-messaging AMQP bus and send messages over it.
    """

    bus_type = "fedora-messaging"

    def __init__(self, opts, log=None):
        super(MsgBusFedoraMessaging, self).__init__(opts, log)
        # note this is not thread safe, only one bus of this type!
        os.environ['FEDORA_MESSAGING_CONF'] = opts.toml_config

    def _send_message(self, message):
        from fedora_messaging import api as fm_api, exceptions as fm_ex
        fm_api.publish(message)


class MessageSender:
    """
    Automatically send messages to all configured buses.
    """
    def __init__(self, backend_opts, name, log):
        self.log = log
        self.name = name

        msg_buses = []
        for bus_config in backend_opts.msg_buses:
            if bus_config.bus_type == 'stomp':
                msg_buses.append(MsgBusStomp(bus_config, log))
            elif bus_config.bus_type == 'fedora-messaging':
                msg_buses.append(MsgBusFedoraMessaging(bus_config, log))

        if backend_opts.fedmsg_enabled:
            msg_buses.append(MsgBusFedmsg(log))

        self.msg_buses = msg_buses
        self.pid = os.getpid()

    def announce(self, topic, job, host):
        """ Send message to all configured buses """
        for bus in self.msg_buses:
            self.log.info("Sending %s message in %s", bus.info, topic)
            bus.announce_job(
                topic, job,
                who=self.name,
                ip=host,
                pid=self.pid
            )
