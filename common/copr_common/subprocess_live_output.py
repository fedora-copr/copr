"""
Streamed reading of Popen() stdout and stderr:

    proc = PosixPipedProcess(["command"])
    for chunk, output = proc.readchunks()
        assert output in ["stdout", "stderr"]
        process(chunk)
"""

from subprocess import Popen, PIPE
from threading import Thread
from queue import Queue
import select
import time

EOF = 0
CUT = 1
LOOP = 2
TIMEOUT = 3
ERR = -1

def _pipe_consumer_thread(pipe, queue, identifier, maxlen=None, poll=5.0):
    """
    Read the PIPE in a separate thread, and enqueue the chunks of output into
    the QUEUE.  The chunks are stored as:
        [(pipename, chunk), ...,  # normal chunks (of bytes)
         (pipename, EOF|CUT|ERR), # pre-termination sequence
         None,                    # iter(sentinel) (stop iteration)
        ]
    """
    counter = 0
    fd = pipe.fileno()
    try:
        while True:
            readable, _, exc = select.select([fd], [], [fd], poll)
            if exc:
                queue.put((identifier, ERR))
                break

            if not readable:
                queue.put((identifier, LOOP))
                continue

            # We need read1() to accept partial reads.
            # https://docs.python.org/3/library/io.html#io.BufferedIOBase.read1
            chunk = pipe.read1(1024)
            if not chunk:
                queue.put((identifier, EOF))
                break

            if maxlen:
                remains = maxlen - counter
                counter += len(chunk)
                if counter > maxlen:
                    chunk = chunk[:remains]
                    queue.put((identifier, chunk))
                    queue.put((identifier, CUT))
                    break

            # send a "normal" continuous chunk to the reader
            queue.put((identifier, chunk))

    finally:
        # Always notify the parent process that we quit!
        queue.put(None)


class PosixPipedProcess:
    """
    Start command using subprocess.Popen() and allow streamed reading of its
    stdout and stderr outputs.
    """
    def __init__(self, command, timeout=None, stdout_limit=None,
                 stderr_limit=None, poll=5.0, **kwargs):
        self.command = command
        self.kwargs = kwargs
        self.stdout_limit = stdout_limit
        self.stderr_limit = stderr_limit
        self.returncode = None
        self.started = None
        self._stopreason = None
        self.killed = None
        self.timeout = timeout
        self.poll = poll

    def timeouted(self):
        """ Return True if process timeouted """
        if not self.timeout:
            return False
        return time.time() - self.started > self.timeout

    def has_cut(self):
        """ Return true if the stdout_limit or stderr_limit is reached """
        return self.stopreason == CUT

    @property
    def stopreason(self):
        """
        Get the reason for stop.
        """
        return self._stopreason


    @stopreason.setter
    def stopreason(self, reason):
        """
        Set the stop reason to EOF, CUT, TIMEOUT or ERR
        """
        if self._stopreason != EOF:
            return
        self._stopreason = reason

    def readchunks(self):
        """
        (line, type)
        (line, type)
        (None: "error string") => Error
        (None: None)           => EOF
        """
        self.returncode = None
        self.started = time.time()
        self.killed = False
        self._stopreason = EOF
        que = Queue()

        # EL7: no __enter__ support in EL7
        # pylint: disable=consider-using-with
        process = Popen(self.command, stdout=PIPE, stderr=PIPE, **self.kwargs)
        tout = Thread(target=_pipe_consumer_thread,
                      args=[process.stdout, que, "stdout",
                            self.stdout_limit, self.poll])
        terr = Thread(target=_pipe_consumer_thread,
                      args=[process.stderr, que, "stderr",
                            self.stderr_limit, self.poll])
        tout.start()
        terr.start()
        def _kill():
            if self.killed:
                return
            self.killed = True
            process.kill()

        try:
            # we need to find two sentinels for both stdout/stderr
            for _ in [1, 2]:
                for fd, chunk in iter(que.get, None):
                    if self.timeouted():
                        self.stopreason = TIMEOUT
                        _kill()

                    if not isinstance(chunk, int):
                        assert chunk
                        yield (chunk, fd)
                        continue

                    if chunk == LOOP:
                        continue

                    # one of the streams ended
                    if chunk in [CUT, ERR]:
                        self.stopreason = chunk
                        _kill()
                        continue

                    assert chunk == EOF
        finally:
            # Subprocesses and threads need to finish.
            process.wait()
            terr.join()
            tout.join()
            self.returncode = process.returncode
