"""
Allocate VMs
"""

import time
from resalloc.client import Connection as ResallocConnection


class RemoteHostAllocationTerminated(Exception):
    """ raised when something happened during VM allocation """


class RemoteHost:
    """
    Remote host allowing us to ssh.
    """
    hostname = None

    _is_ready = False
    _sleeptime = 5
    _sleeptime_history = {}
    _factory = None

    def check_ready(self):
        """
        Check that the host is ready (usually it means that it is ready to talk
        over ssh layer).
        :raises RemoteHostAllocationTerminated exception.
        """
        raise NotImplementedError

    def release(self):
        """
        Declare that we don't need this host anymore.  It is up to the VM
        provider what it will do with this host.
        """
        raise NotImplementedError

    def _check_ready(self):
        if self._is_ready:
            return True
        self._is_ready = self.check_ready()
        return self._is_ready

    @property
    def info(self):
        """ user-readable info about the host """
        return "no info"

    @staticmethod
    def _incremental_sleep(sleeptimes=None):
        """
        Wait cca two minutes with faster cadence, and then fallback to one
        minute sleep.
        """
        counter = 0
        if sleeptimes is None:
            # wait cca two minutes, then fallback to 60s sleep(s)
            sleeptimes = [3, 3, 6, 6, 10, 10, 10, 20, 20, 20, 30]

        while True:
            try:
                sleeptime = sleeptimes[counter]
            except IndexError:
                sleeptime = 60
            time.sleep(sleeptime)
            yield
            counter += 1

    def wait_ready(self):
        """
        Passively wait till self.is_ready is true.  Return True if we
        successfully waited for the VM.
        """
        sleep = self._incremental_sleep()
        try:
            while True:
                if self._check_ready():
                    return True
                next(sleep)
        except RemoteHostAllocationTerminated:
            pass
        return False


class ResallocHost(RemoteHost):
    """
    VM representation, and box allocation mechanism using pre-configured
    resalloc server:
    https://github.com/praiskup/resalloc
    """
    ticket = None

    def check_ready(self):
        self.ticket.collect()
        if self.ticket.closed:
            # canceled, or someone else closed the ticket
            raise RemoteHostAllocationTerminated
        if not self.ticket.ready:
            return False
        self.hostname = str(self.ticket.output).strip()
        return True

    def release(self):
        self.ticket.close()

    @property
    def info(self):
        message = "ResallocHost"
        if self.ticket:
            message += ", ticket_id={}".format(self.ticket.id)
        if self.hostname:
            message += ", hostname={}".format(self.hostname)
        return message


class HostFactory:
    """ Abstract host provider """
    def get_host(self, tags=None, sandbox=None):
        """
        Return new box instance which is not yet ready.  It is up to the caller
        to wait.
        """
        raise NotImplementedError


class ResallocHostFactory(HostFactory):
    """
    Provide worker hosts using resalloc server:
    https://github.com/praiskup/resalloc
    """
    def __init__(self, server="http://localhost:49100"):
        self.conn = ResallocConnection(
            server, request_survives_server_restart=True)

    def get_host(self, tags=None, sandbox=None):
        request_tags = ["copr_builder"]
        if tags:
            request_tags.extend(tags)

        host = ResallocHost()
        host.ticket = self.conn.newTicket(request_tags, sandbox)
        return host
