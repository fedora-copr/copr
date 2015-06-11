# coding: utf-8
import json
import os
import re
from setproctitle import setproctitle
from threading import Thread
import time
from multiprocessing import Process

from IPy import IP

from ..ans_utils import run_ansible_playbook_cli
from backend.helpers import get_redis_connection
from backend.vm_manage import PUBSUB_MB, EventTopics
from backend.vm_manage.executor import Executor
from ..exceptions import CoprSpawnFailError
from ..helpers import get_redis_logger


def spawn_instance(spawn_playbook, log):
    """
    Spawn new VM, executing the following steps:

        - call the spawn playbook to startup/provision a building instance
        - get an IP and test if the builder responds
        - repeat this until you get an IP of working builder

    :type log: logging.Logger
    :return: dict with ip and name of created VM
    :raises CoprSpawnFailError:
    """
    log.info("Spawning a builder")

    start = time.time()
    # Ansible playbook python API does not work here, dunno why.  See:
    # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

    spawn_args = "-c ssh {}".format(spawn_playbook)
    try:
        result = run_ansible_playbook_cli(spawn_args, comment="spawning instance", log=log)
    except Exception as err:
        raise CoprSpawnFailError("Error during ansible invocation: {}".format(err.__dict__))

    if not result:
        raise CoprSpawnFailError("No result, trying again")
    match = re.search(r'IP=([^\{\}"\n\\]+)', result, re.MULTILINE)

    if not match:
        raise CoprSpawnFailError("No ip in the result, trying again")
    ipaddr = match.group(1)
    match = re.search(r'vm_name=([^\{\}"\n\\]+)', result, re.MULTILINE)

    if match:
        vm_name = match.group(1)
    else:
        raise CoprSpawnFailError("No vm_name in the playbook output")

    try:
        IP(ipaddr)
    except ValueError:
        # if we get here we"re in trouble
        msg = "Invalid IP: `{}` back from spawn_instance - dumping cache output\n".format(ipaddr)
        msg += str(result)
        raise CoprSpawnFailError(msg)

    log.info("Got VM {} ip: {}. Instance spawn/provision took {} sec"
             .format(vm_name, ipaddr, time.time() - start))
    return {"vm_ip": ipaddr, "vm_name": vm_name}


def do_spawn_and_publish(opts, spawn_playbook, group):
    # setproctitle("do_spawn_and_publish")

    log = get_redis_logger(opts, "spawner.detached", "spawner")

    try:
        log.debug("Going to spawn")
        spawn_result = spawn_instance(spawn_playbook, log)
        log.debug("Spawn finished")
    except CoprSpawnFailError as err:
        log.exception("Failed to spawn builder: {}".format(err))
        return
    except Exception as err:
        log.exception("[Unexpected] Failed to spawn builder: {}".format(err))
        return

    spawn_result["group"] = group
    spawn_result["topic"] = EventTopics.VM_SPAWNED
    try:
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(spawn_result))
    except Exception as err:
        log.exception("Failed to publish msg about new VM: {} with error: {}"
                      .format(spawn_result, err))


class Spawner(Executor):
    __name_for_log__ = "spawner"
    __who_for_log__ = "spawner"

    def start_spawn(self, group):
        try:
            spawn_playbook = self.opts.build_groups[group]["spawn_playbook"]
        except KeyError:
            msg = "Config missing spawn playbook for group: {}".format(group)
            raise CoprSpawnFailError(msg)

        if spawn_playbook is None:
            msg = "Missing spawn playbook for group: {} for unknown reason".format(group)
            raise CoprSpawnFailError(msg)

        if not os.path.exists(spawn_playbook):
            msg = "Spawn playbook {} is missing".format(spawn_playbook)
            raise CoprSpawnFailError(msg)

        self.run_detached(do_spawn_and_publish, args=(self.opts, spawn_playbook, group))

        # proc = Process(target=do_spawn_and_publish, args=(self.opts, spawn_playbook, group))
        # proc = Thread(target=do_spawn_and_publish, args=(self.opts, spawn_playbook, group))
        # self.child_processes.append(proc)
        # proc.start()
        # self.log.debug("Spawn process started: {}".format(proc.pid))
