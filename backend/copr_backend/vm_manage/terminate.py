# coding: utf-8
import json
import os
import time
from copr_backend.ans_utils import ans_extra_vars_encode, run_ansible_playbook_cli
from copr_backend.exceptions import CoprSpawnFailError
from copr_backend.helpers import get_redis_connection
from copr_backend.vm_manage import EventTopics, PUBSUB_MB
from copr_backend.vm_manage.executor import Executor
from ..helpers import get_redis_logger


def terminate_vm(opts, terminate_playbook, group, vm_name, vm_ip):
    """
    Call the terminate playbook to destroy the instance
    """
    log = get_redis_logger(opts, "terminator.detached", "terminator")

    term_args = {"ip": vm_ip, "vm_name": vm_name}

    args = "-c ssh {} {}".format(
        # self.vm_ip,
        terminate_playbook,
        ans_extra_vars_encode(term_args, "copr_task"))

    result = {
        "vm_ip": vm_ip,
        "vm_name": vm_name,
        "group": group,
        "topic": EventTopics.VM_TERMINATED,
        "result": "OK"
    }
    start_time = time.time()
    try:
        log.info("starting terminate vm with args: %s", term_args)
        run_ansible_playbook_cli(args, "terminate instance", log)
        result["result"] = "OK"
    except Exception as error:
        result["result"] = "failed"
        msg = "Failed to terminate an instance: vm_name={}, vm_ip={}, error: {}".format(vm_name, vm_ip, error)
        result["msg"] = msg
        log.exception(msg)

    try:
        log.info("VM terminated %s, time elapsed: %s ", term_args, time.time() - start_time)
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(result))
    except Exception as error:
        log.exception("Failed to publish msg about new VM: %s with error: %s", result, error)


class Terminator(Executor):

    __name_for_log__ = "terminator"
    __who_for_log__ = "terminator"

    def terminate_vm(self, vm_ip, vm_name, group):
        self.recycle()

        try:
            terminate_playbook = self.opts.build_groups[int(group)]["terminate_playbook"]
        except KeyError:
            msg = "Config missing termination playbook for group: {}".format(group)
            raise CoprSpawnFailError(msg)

        if terminate_playbook is None:
            msg = "Missing terminate playbook for group: {} for unknown reason".format(group)
            raise CoprSpawnFailError(msg)

        if not os.path.exists(terminate_playbook):
            msg = "Termination playbook {} is missing".format(terminate_playbook)
            raise CoprSpawnFailError(msg)

        self.log.info("received VM ip: %s, name: %s for termination", vm_ip, vm_name)

        self.run_detached(terminate_vm, args=(self.opts, terminate_playbook, group, vm_name, vm_ip))
