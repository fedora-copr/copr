# coding: utf-8
import json
import subprocess
from subprocess import CalledProcessError
import sys

ansible_playbook_bin = "ansible-playbook"


def ans_extra_vars_encode(extra_vars, name):
    """ transform dict into --extra-vars="json string" """
    if not extra_vars:
        return ""
    return "--extra-vars='{{\"{0}\": {1}}}'".format(name, json.dumps(extra_vars))


def run_ansible_playbook_cli(args, name="running playbook", log_fn=None):
    if log_fn is None:
        log = lambda x: sys.stderr.write("{}\n".format(x))
    else:
        log = log_fn

    command = "{} {}".format(ansible_playbook_bin, args)
    try:
        log("{}: begin: {}".format(name, command))
        result = subprocess.check_output(command, shell=True)
        log("Raw playbook output: {0}".format(result))
    except CalledProcessError as e:
        log("CalledProcessError: {}".format(e.output))
        # FIXME: this is not purpose of opts.sleeptime
        raise

    log(name + ": end")
    return result
