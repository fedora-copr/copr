# coding: utf-8
import json
import subprocess
from subprocess import CalledProcessError

ansible_playbook_bin = "ansible-playbook"


def ans_extra_vars_encode(extra_vars, name):
    """ transform dict into --extra-vars="json string" """
    if not extra_vars:
        return ""
    return "--extra-vars='{{\"{0}\": {1}}}'".format(name, json.dumps(extra_vars))


def run_ansible_playbook_cli(args, comment, log, timeout=None):
    """
    :param args:
    :param comment:
    :param timeout:
    :type log: logging.Logger
    :return: ansible output
    """
    command = "{} -v {}".format(ansible_playbook_bin, args)

    if comment is None:
        comment = "running playbook"
    if timeout:
        command = "timeout {} {}".format(timeout, command)

    try:
        log.info("%s: begin: %s", comment, command)
        result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT, encoding="utf-8")
    except CalledProcessError as e:
        log.info("CalledProcessError: %s", e.output)
        raise

    log.debug(comment + ": end")
    return result
