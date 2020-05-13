"""
Allocate VMs
"""

import time
from resalloc.client import Connection as ResallocConnection


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
        Passively wait till self.is_ready is true.
        """
        sleep = self._incremental_sleep()
        while not self._check_ready():
            next(sleep)
        return True


class ResallocHost(RemoteHost):
    """
    VM representation, and box allocation mechanism using pre-configured
    resalloc server:
    https://github.com/praiskup/resalloc
    """
    ticket = None

    def check_ready(self):
        if self.ticket.collect():
            self.hostname = str(self.ticket.output).strip()
            return True
        return False

    def release(self):
        self.ticket.close()


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
