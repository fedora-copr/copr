import logging
import os
import time
import subprocess

import netaddr

class SSHConnectionError(Exception):
    pass

class SSHConnection(object):
    """
    SSH connection representation.

    This class heavily depedns on the native openssh client configuration file
    (man 5 sh_config).  The example configuration might be:

        $ cat /home/copr/.ssh/builder_config
        Host *
        # For dynamically started VMs.
        StrictHostKeyChecking no
        UserKnownHostsFile /dev/null

        # For non-default paths to identity file.
        IdentityFile ~/.ssh/id_rsa_copr

        # Ensure remote command uses proper line buffering for live logs
        # (so called live logs).
        RequestTTY=force

        # Keep control sockets open, to speedup subsequent command runs.
        ControlPath=/home/copr/ssh_socket_%h_%p_%r
        ControlMaster=auto
        ControlPersist=900

    Then just use:
    SSHConnection(user='mockbuilder', host=vm_ip,
                  config_file='/home/copr/.ssh/builder_config')

    :param user:
        Remote user name.  'root' by default.
    :param host:
        Remote hostname or IP.  'localhost' by default.
    :param  config_file:
        Full (absolute) path ssh config file to be used.  None by default means
        the default ssh configuration is used /etc/ssh_config and ~/.ssh/config.
    """

    def __init__(self, user=None, host=None, config_file=None, log=None):
        # TODO: Some of the calling code places heavily re-try the ssh
        # connection..  There's a some small chance that the host goes down, and
        # some other host is started with the same hostname (or IP address).
        # Therefore we should remember the host's SSH fingerprint here and check
        # it when reconnecting.
        self.config_file = config_file
        self.user = user or 'root'
        self.host = host or 'localhost'
        if log:
            self.log = log
        else:
            self.log = logging.getLogger()

    def _ssh_base(self):
        cmd = ['ssh']
        if self.config_file:
            cmd = cmd + ['-F', self.config_file]
        cmd.append('{0}@{1}'.format(self.user, self.host))
        return cmd

    def _run(self, user_command, stdout, stderr):
        real_command = self._ssh_base() + [user_command]
        proc = subprocess.Popen(real_command, stdout=stdout, stderr=stderr, encoding="utf-8")
        retval = proc.wait()
        if retval == 255:
            # Because we don't manage the control path (that's done in ssh
            # configuration), we can not really check that 255 exit status is
            # ssh connection error, or command error.
            raise SSHConnectionError("Connection broke.")

        return retval

    def run(self, user_command, stdout=None, stderr=None, max_retries=0):
        """
        Run user_command (blocking) and redirect stdout and/or stderr into
        pre-opened python file descriptor.  When stdout/stderr is not set, the
        output from particular command is ignored.

        :param user_command:
            Command (string) to be executed (note: use shlex.quote).

        :param max_retries:
            When there is ssh connection problem, re-try the action at most
            ``max_retries`` times.  Default is no re-try.  Note that we write
            the output from all the re-tries to the stdout/stderr descriptors
            (when specified).

        :param stdout:
            File descriptor to write standard output into.

        :param stderr:
            File descriptor to write standard error output into.

        :returns:
            Exit status of remote program, or -1 when unexpected failure occurs.

        :type command: str
        :type stdout: file or None
        :type stderr: file or None
        :rtype: list

        """
        rc = -1
        with open(os.devnull, "w") as devnull:
            rc = self._retry(self._run, max_retries,
                             user_command, stdout or devnull, stderr or devnull)
        return rc

    def run_expensive(self, user_command, max_retries=0):
        """
        Run user_command (blocking) and return exit status together with
        standard outputs in string variables.  Note that this can pretty easily
        waste a lot of memory, run() is better option.

        :param user_command:
            Command (string) to be run as string (note: use shlex.quote).

        :param max_retries:
            When there is ssh connection problem, re-try the action at most
            ``max_retries`` times.  Default is no re-try.

        :returns:
            Tripple (rc, stdout, stderr).  Stdout and stderr are strings, those
            might be pretty large.
        """
        return self._retry(self._run_expensive, max_retries, user_command)

    def _run_expensive(self, user_command):
        real_command = self._ssh_base() + [user_command]
        proc = subprocess.Popen(real_command, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, encoding="utf-8")
        stdout, stderr = proc.communicate()
        if proc.returncode == 255:
            # Value 255 means either that 255 was returned by remote command or
            # the ssh connection broke.  Because we need to handle "Connection
            # broke" issues (resubmit build e.g.), please avoid situations when
            # remote command returns value 255 (or -1).
            raise SSHConnectionError(
                "Connection broke:\nOUT:\n{0}\nERR:\n{1}".format(
                    stdout, stderr))

        return proc.returncode, stdout, stderr

    def _retry(self, method, retries, *args, **kwargs):
        """ Do ``times`` when SSHConnectionError is raised """
        attempt = 0
        while attempt < retries + 1:
            attempt += 1
            try:
                return method(*args, **kwargs)
            except SSHConnectionError as exc:
                sleep = 10
                self.log.error("SSH connection lost on #%s attempt, "
                               "let's retry after %ss, %s", attempt, sleep, exc)
                time.sleep(sleep)
                continue
        raise SSHConnectionError("Unable to finish after {} SSH attempts"
                                 .format(attempt))

    def _full_source_path(self, src):
        """ for easier unittesting """
        host = self.host
        if netaddr.valid_ipv6(host):
            host = "[{}]".format(host)
        return "{}@{}:{}".format(self.user, host, src)

    def rsync_download(self, src, dest, logfile=None, max_retries=0):
        """
        Run rsync over pre-allocated socket (by the config)

        :param src:
            Source path on self.host to copy.

        :param dest:
            Destination path on backend to copy ``src` content to.

        :param max_retries:
            When there is ssh connection problem, re-try the action at most
            ``max_retries`` times.  Default is no re-try.

        Store the logs to ``logfile`` within ``dest`` directory.  The dest
        directory needs to exist.
        """
        self._retry(self._rsync_download, max_retries, src, dest, logfile)

    def _rsync_download(self, src, dest, logfile=None):
        ssh_opts = "ssh"
        if self.config_file:
            ssh_opts += " -F " + self.config_file

        full_source_path = self._full_source_path(src)

        log_filepath = "/dev/null"
        if logfile:
            log_filepath = os.path.join(dest, logfile)
        command = "/usr/bin/rsync -rltDvH --chmod=D755,F644 -e '{}' {} {}/ &> {}".format(
            ssh_opts, full_source_path, dest, log_filepath)

        try:
            self.log.info("rsyncing of %s to %s started", full_source_path, dest)
            cmd = subprocess.Popen(command, shell=True)
            cmd.wait()
            self.log.info("rsyncing finished.")
        except Exception as error:
            self.log.error(
                "Failed to download data from builder due to Popen error, "
                "original error: %s", error)
            raise SSHConnectionError("POpen failure in rsync.")

        if cmd.returncode != 0:
            err_msg = (
                "Failed to download data from builder due to rsync error, "
                "see the rsync log file for details."
            )
            self.log.error(err_msg)
            raise SSHConnectionError(err_msg)
