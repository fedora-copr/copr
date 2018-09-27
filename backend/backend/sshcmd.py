import os
import subprocess

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

    def __init__(self, user=None, host=None, config_file=None):
        self.config_file = config_file
        self.user = user or 'root'
        self.host = host or 'localhost'

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

    def run(self, user_command, stdout=None, stderr=None):
        """
        Run user_command (blocking) and redirect stdout and/or stderr into
        pre-opened python file descriptor.  When stdout/stderr is not set, the
        output from particular command is ignored.

        :param user_command:
            Command (string) to be executed (note: use pipes.quote).

        :param stdout:
            File descriptor to write standard output into.

        :param stderr:
            File descriptor to write standard error output into.

        :returns:
            Triple (rc, stdout, stderr).  Stdout and stderr are of type str,
            and might be pretty large.

        :type command: str
        :type stdout: file or None
        :type stderr: file or None
        :rtype: list

        """
        rc = -1
        with open(os.devnull, "w") as devnull:
            rc = self._run(user_command, stdout or devnull, stderr or devnull)
        return rc

    def run_expensive(self, user_command):
        """
        Run user_command (blocking) and return exit status together with
        standard outputs in string variables.  Note that this can pretty easily
        waste a lot of memory, run() is better option.

        :param user_command:
            Command (string) to be run as string (note: use pipes.quote).

        :returns:
            Tripple (rc, stdout, stderr).  Stdout and stderr are strings, those
            might be pretty large.
        """
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
