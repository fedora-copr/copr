"""
Message buses abstraction.
"""

import logging
import copy
import json

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


class _LogAdapter(logging.LoggerAdapter):
    def process(self, msg, kwargs):
        return "[BUS '{0}'] {1}".format(self.extra['bus_id'], msg), kwargs


class MsgBus(object):
    """
    An "abstract" message bus class, don't instantiate!
    """
    messages = {}

    def __init__(self, opts, log=None):
        self.opts = opts
        # Fix bus_id soon enough.
        self.opts.bus_id = getattr(self.opts, 'bus_id', type(self).__name__)

        if not log:
            log = logging
            logging.basicConfig(level=logging.DEBUG)

        self.log = _LogAdapter(log, {'bus_id': self.opts.bus_id})

        self.log.info("initializing bus")
        if hasattr(self.opts, 'messages'):
            self.messages.update(self.opts.messages)


    def _send(self, topic, body, headers):
        raise NotImplementedError


    def send(self, topic, body, headers=None):
        """
        Send (dict) message over _send() method.
        """
        out_headers = copy.deepcopy(self.opts.headers)
        if headers:
            out_headers.update(copy.deepcopy(headers))
        try:
            self._send(topic, body, out_headers)
        # pylint: disable=W0703
        except Exception as _:
            self.log.exception("Failed to publish message.")


    def announce_job(self, topic, job, **kwargs):
        """
        Announce everywhere that a build process started now.
        """
        if not topic in self.messages:
            return


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
        content.update(kwargs)

        msg = {}
        try:
            for key in self.messages[topic]:
                msg[key] = self.messages[topic][key].format(**content)
        # pylint: disable=W0703
        except Exception as _:
            self.log.exception("Failed to format '{0}' announcement."
                               .format(topic))
            return

        self.send(topic, msg)


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

    def connect(self):
        """
        connect (even repeatedly) to STOMP message bus
        """
        self.conn.start()
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


    def _send(self, topic, body, headers):
        send_headers = copy.deepcopy(headers)
        send_headers['topic'] = topic
        self.conn.send(body=json.dumps(body), headers=send_headers,
                       destination=self.opts.destination,
                       content_type='application/json')


class MsgBusFedmsg(MsgBus):
    """
    Connect to fedmsg and send messages over it.
    """
    messages = {
        'build.start': {
            'what': "build start: user:{user} copr:{copr}" \
                    " pkg:{pkg} build:{build} ip:{ip} pid:{pid}",
        },
        'chroot.start': {
            'what': "chroot start: chroot:{chroot} user:{user}" \
                    " copr:{copr} pkg:{pkg} build:{build} ip:{ip} pid:{pid}",
        },
        'build.end': {
            'what': "build end: user:{user} copr:{copr} build:{build}" \
                    " pkg:{pkg} version:{version} ip:{ip} pid:{pid} status:{status}",
        },
    }

    def __init__(self, log=None):
        # Hack to not require opts argument for now.
        opts = type('', (), {})
        opts.headers = {}

        super(MsgBusFedmsg, self).__init__(opts, log)

        fedmsg.init(name='relay_inbound', cert_prefix='copr', active=True)

    def announce_job(self, topic, job, **kwargs):
        """
        Announce everywhere that a build process started now.
        """
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
        content.update(kwargs)

        if topic in self.messages:
            for key in self.messages[topic]:
                content[key] = self.messages[topic][key].format(**content)

        self.send(topic, content)

    def _send(self, topic, content, headers):
        fedmsg.publish(modname='copr', topic=topic, msg=content)
