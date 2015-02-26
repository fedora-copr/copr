# coding: utf-8
import json
import os

import re

from pprint import pprint
from setproctitle import setproctitle
import weakref
from IPy import IP
import time
from multiprocessing import Process, Queue
from redis import StrictRedis
import sys

from ..ans_utils import run_ansible_playbook_cli
from backend.helpers import get_redis_connection, format_tb
from backend.vm_manage import PUBSUB_MB, EventTopics
from backend.vm_manage.executor import Executor
from ..exceptions import CoprSpawnFailError


# def try_spawn(args, log_fn=None):
#     """
#     Tries to spawn new vm using ansible
#
#     :param args: ansible for ansible command which spawns VM
#     :return str: valid ip address of new machine (nobody guarantee machine availability)
#     """
#     if log_fn is None:
#         log_fn = lambda x: pprint(x)
#
#     result = run_ansible_playbook_once(args, name="spawning instance")
#
#     if not result:
#         raise CoprSpawnFailError("No result, trying again")
#     match = re.search(r'IP=([^\{\}"]+)', result, re.MULTILINE)
#
#     if not match:
#         raise CoprSpawnFailError("No ip in the result, trying again")
#     ipaddr = match.group(1)
#     match = re.search(r'vm_name=([^\{\}"]+)', result, re.MULTILINE)
#
#     if match:
#         vm_name = match.group(1)
#     else:
#         raise CoprSpawnFailError("No vm_name in the playbook output")
#     log_fn("got instance ip: {0}".format(ipaddr))
#
#     try:
#         IP(ipaddr)
#     except ValueError:
#         # if we get here we"re in trouble
#         msg = "Invalid IP back from spawn_instance - dumping cache output\n"
#         msg += str(result)
#         raise CoprSpawnFailError(msg)
#
#     return {"ip": ipaddr, "vm_name": vm_name}
#

def spawn_instance(spawn_playbook, log_fn):
    """
    Spawn new VM, executing the following steps:

        - call the spawn playbook to startup/provision a building instance
        - get an IP and test if the builder responds
        - repeat this until you get an IP of working builder

    :param BuildJob job:
    :return ip: of created VM
    :return None: if couldn't find playbook to spin ip VM
    """
    log_fn("Spawning a builder")

    start = time.time()
    # Ansible playbook python API does not work here, dunno why.  See:
    # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

    spawn_args = "-c ssh {}".format(spawn_playbook)
    try:
        result = run_ansible_playbook_cli(spawn_args, name="spawning instance", log_fn=log_fn)
    except Exception as err:
        raise CoprSpawnFailError("Error during ansible invocation: {}".format(err.__dict__))

    if not result:
        raise CoprSpawnFailError("No result, trying again")
    match = re.search(r'IP=([^\{\}"]+)', result, re.MULTILINE)

    if not match:
        raise CoprSpawnFailError("No ip in the result, trying again")
    ipaddr = match.group(1)
    match = re.search(r'vm_name=([^\{\}"]+)', result, re.MULTILINE)

    if match:
        vm_name = match.group(1)
    else:
        raise CoprSpawnFailError("No vm_name in the playbook output")
    log_fn("got instance ip: {0}".format(ipaddr))

    try:
        IP(ipaddr)
    except ValueError:
        # if we get here we"re in trouble
        msg = "Invalid IP: `{}` back from spawn_instance - dumping cache output\n".format(ipaddr)
        msg += str(result)
        raise CoprSpawnFailError(msg)

    log_fn("Instance spawn/provision took {0} sec".format(time.time() - start))
    return {"vm_ip": ipaddr, "vm_name": vm_name}


def do_spawn_and_publish(opts, events, spawn_playbook, group):
    setproctitle("do_spawn_and_publish")

    def log_fn(msg):
        events.put({"when": time.time(), "who": "spawner", "what": msg})
        # rc = get_redis_connection(opts)
        # rc.publish("debug", str(msg))

    try:
        log_fn("Going to spawn")
        spawn_result = spawn_instance(spawn_playbook, log_fn)
        log_fn("Spawn finished")
    except CoprSpawnFailError as err:
        log_fn("Failed to spawn builder: {}".format(err))
        return
    except Exception as err:
        log_fn("[Unexpected] Failed to spawn builder: {}".format(err))
        return

    spawn_result["group"] = group
    spawn_result["topic"] = EventTopics.VM_SPAWNED
    try:
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(spawn_result))
    except Exception as err:
        log_fn("Failed to publish msg about new VM: {} with error: {}"
               .format(spawn_result, err))


class Spawner(Executor):
    __name_for_log__ = "spawner"

    def start_spawn(self, group):
        self.recycle()
        spawn_playbook = None
        try:
            spawn_playbook = self.opts.build_groups[group]["spawn_playbook"]
        except KeyError:
            msg = "Config missing spawn playbook for group: {}".format(group)
            self.log(msg)
            raise CoprSpawnFailError(msg)

        if spawn_playbook is None:
            msg = "Missing spawn playbook for group: {} for unknown reason".format(group)
            raise CoprSpawnFailError(msg)

        if not os.path.exists(spawn_playbook):
            msg = "Spawn playbook {} is missing".format(spawn_playbook)
            self.log(msg)
            raise CoprSpawnFailError(msg)

        proc = Process(target=do_spawn_and_publish,
                       args=(self.opts, self.events, spawn_playbook, group))
        self.child_processes.append(proc)
        proc.start()
        self.log("Spawn process started: {}".format(proc.pid))
