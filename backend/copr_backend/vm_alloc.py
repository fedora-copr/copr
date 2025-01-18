"""
Allocate VMs
"""

import time
import yaml
from resalloc.client import Connection as ResallocConnection


class RemoteHostAllocationTerminated(Exception):
    """ raised when something happened during VM allocation """


class RemoteHost:
    """
    Remote host allowing us to ssh.
    """
    hostname = None

    _is_ready = False

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
    name = None
    requested_tags = None

    def parse_ticket_data(self):
        """
        Historically we expected a single-line input containing hostname/IP.  We
        continue to support this format.  But if the output looks like YAML
        document, we parse the output and detect additional metadata.
        """
        output = str(self.ticket.output)
        lines = output.split("\n")
        if lines[0] == "---":
            try:
                data = yaml.safe_load(output)
                # We expect IP or hostname here
                self.hostname = data["host"]
                # RESALLOC_NAME
                self.name = data["name"]
            except yaml.YAMLError as exc:
                raise RemoteHostAllocationTerminated(
                    f"Can't parse YAML data from the resalloc ticket:\n{output}") from exc
            except KeyError as exc:
                raise RemoteHostAllocationTerminated(
                    f"Missing YAML fields in the resalloc ticket output\n{output}") from exc
        else:
            # The old format
            self.hostname = lines[0]

    def check_ready(self):
        self.ticket.collect()
        if self.ticket.closed:
            # canceled, or someone else closed the ticket
            raise RemoteHostAllocationTerminated
        if not self.ticket.ready:
            return False
        self.parse_ticket_data()
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
        if self.name:
            message += ", name={}".format(self.name)
        if self.requested_tags:
            message += f", requested_tags={self.requested_tags}"
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
        host.requested_tags = request_tags
        return host
