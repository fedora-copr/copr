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
except ImportError:
    # stomp is also optional
    stomp = None

class MsgBus(object):
    """
    An "abstract" message bus class, don't instantiate!
    """
    messages = {}

    def __init__(self, opts, log=None):
        if not log:
            log = logging
            logging.basicConfig(level=logging.DEBUG)

        self.log = log
        self.opts = opts

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


class MsgBusStomp(MsgBus):
    """
    Connect to STOMP bus and send messages.  Make sure you have correctly
    configured 'messages' attribute in every message bus configuration, no
    default messages here!
    """

    def __init__(self, opts, log=None):
        super(MsgBusStomp, self).__init__(opts, log)

        # shortcuts
        host = self.opts.host
        port = int(self.opts.port)
        username = None
        password = None

        self.log.info("connecting to (stomp) message bus '{0}:{1}"
                      .format(host, port))
        self.conn = stomp.Connection([(host, int(port))])
        self.conn.start()

        if getattr(self.opts, 'auth', None):
            username = self.opts.auth['username']
            password = self.opts.auth['password']
            self.log.info("authenticating with username '{0}'".format(username))

        self.conn.connect(
            username=username,
            passcode=password,
        )

        if not getattr(self.opts, 'destination', None):
            setattr(self.opts, 'destination', '/default')


    def _send(self, topic, body, headers):
        send_headers = copy.deepcopy(headers)
        send_headers['topic'] = topic
        self.conn.send(body=json.dumps(body), headers=send_headers,
                       destination=self.opts.destination)


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
