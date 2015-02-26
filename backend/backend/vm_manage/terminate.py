# coding: utf-8
import json
import os
from setproctitle import setproctitle
import weakref
import time
from multiprocessing import Process
import sys
from backend.ans_utils import ans_extra_vars_encode, run_ansible_playbook_cli
from backend.exceptions import CoprSpawnFailError
from backend.helpers import format_tb, get_redis_connection
from backend.vm_manage import EventTopics, PUBSUB_MB
from backend.vm_manage.executor import Executor


def terminate_vm(opts, events, terminate_playbook, group, vm_name, vm_ip):
    """
    Call the terminate playbook to destroy the instance
    """
    setproctitle("Terminating VM")

    def log_fn(msg):
        events.put({"when": time.time(), "who": "terminate_proc", "what": msg})

    term_args = {
        "ip": vm_ip,
        "vm_name": vm_name,
    }
    # if "ip" in opts.terminate_vars:
    #     term_args["ip"] = vm_ip
    # if "vm_name" in opts.terminate_vars:
    #     term_args["vm_name"] = vm_name

    # args = "-c ssh -i '{0},' {1} {2}".format(
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
    try:
        log_fn("starting terminate playbook")
        run_ansible_playbook_cli(args, "terminate instance", log_fn=log_fn)
        result["result"] = "OK"
    except Exception as error:
        result["result"] = "failed"
        _, _, ex_tb = sys.exc_info()
        msg = ("Failed to terminate an instance: vm_name={}, vm_ip={}. Original error: {}; {}"
               .format(vm_name, vm_ip, error, format_tb(error, ex_tb)))
        result["msg"] = msg
        log_fn(msg)

    try:
        log_fn("VM terminated, publishing msg")
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(result))
    except Exception as error:
        _, _, ex_tb = sys.exc_info()
        log_fn("Failed to publish msg about new VM: {} with error: {}; {}"
               .format(result, error, format_tb(error, ex_tb)))


class Terminator(Executor):

    __name_for_log__ = "terminator"

    def terminate_vm(self, vm_ip, vm_name, group):
        self.recycle()
        terminate_playbook = None
        try:
            terminate_playbook = self.opts.build_groups[int(group)]["terminate_playbook"]
        except KeyError:
            msg = "Config missing termination playbook for group: {}".format(group)
            self.log(msg)
            raise CoprSpawnFailError(msg)

        if terminate_playbook is None:
            msg = "Missing terminate playbook for group: {} for unknown reason".format(group)
            raise CoprSpawnFailError(msg)

        if not os.path.exists(terminate_playbook):
            msg = "Termination playbook {} is missing".format(terminate_playbook)
            self.log(msg)
            raise CoprSpawnFailError(msg)

        self.log("received VM ip: {}, name: {} for termination".format(vm_ip, vm_name))
        proc = Process(target=terminate_vm, args=(self.opts, self.events,
                                                  terminate_playbook,
                                                  group, vm_name, vm_ip))
        self.child_processes.append(proc)
        proc.start()
        self.log("Termination process started: {}".format(proc.pid))

