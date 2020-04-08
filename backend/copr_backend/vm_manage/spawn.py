# coding: utf-8

import json
import os
import re
import time

from netaddr import IPAddress

from copr_backend.helpers import get_redis_connection
from copr_backend.vm_manage import PUBSUB_MB, EventTopics
from copr_backend.vm_manage.executor import Executor
from ..ans_utils import run_ansible_playbook_cli
from ..exceptions import CoprSpawnFailError
from ..helpers import get_redis_logger
from ..vm_manage import terminate

def get_ip_from_log(ansible_output):
    """ Parse IP address from ansible log """
    match = re.search(r'IP=([^\{\}"\n\\]+)', ansible_output, re.MULTILINE)
    if not match:
        raise CoprSpawnFailError("No ip in the result, trying again")
    return match.group(1)

def get_vm_name_from_log(ansible_output):
    """ Parse vm_name from ansible log """
    match = re.search(r'vm_name=([^\{\}"\n\\]+)', ansible_output, re.MULTILINE)
    if not match:
        raise CoprSpawnFailError("No vm_name in the playbook output")
    return match.group(1)

def spawn_instance(spawn_playbook, log, timeout=None):
    """
    Spawn new VM, executing the following steps:

        - call the spawn playbook to startup/provision a building instance
        - get an IP and test if the builder responds
        - repeat this until you get an IP of working builder

    :type log: logging.Logger
    :return: dict with ip and name of created VM
    :raises CoprSpawnFailError:
    """
    log.info("Spawning a builder with pb: {}".format(spawn_playbook))

    start = time.time()
    # Ansible playbook python API does not work here, dunno why.  See:
    # https://groups.google.com/forum/#!topic/ansible-project/DNBD2oHv5k8

    spawn_args = "-c ssh {}".format(spawn_playbook)
    try:
        result = run_ansible_playbook_cli(spawn_args, comment="spawning instance", log=log, timeout=timeout)
    except Exception as err:
        raise CoprSpawnFailError(str(err.__dict__))

    if not result:
        raise CoprSpawnFailError("No result, trying again")

    ipaddr = get_ip_from_log(result)
    vm_name = get_vm_name_from_log(result)

    try:
        IPAddress(ipaddr)
    except:
        # if we get here we are in trouble
        msg = "Invalid IP: `{}` back from spawn_instance - dumping cache output\n".format(ipaddr)
        msg += str(result)
        raise CoprSpawnFailError(msg)

    log.info("Got VM {} ip: {}. Instance spawn/provision took {} sec"
             .format(vm_name, ipaddr, time.time() - start))
    return {"vm_ip": ipaddr, "vm_name": vm_name}


def do_spawn_and_publish(opts, spawn_playbook, group):

    log = get_redis_logger(opts, "spawner.detached", "spawner")

    try:
        log.debug("Going to spawn")
        timeout = opts.build_groups[int(group)].get("playbook_timeout")
        spawn_result = spawn_instance(spawn_playbook, log, timeout=timeout)
        log.debug("Spawn finished")
    except CoprSpawnFailError as err:
        log.info("Spawning a builder with pb: %s", err.msg)
        vm_ip = get_ip_from_log(err.msg)
        vm_name = get_vm_name_from_log(err.msg)
        if vm_ip and vm_name:
            # VM started but failed later during ansible run.
            try:
                log.exception("Trying to terminate: %s(%s).", vm_name, vm_ip)
                terminate.terminate_vm(opts, opts.build_groups[int(group)]["terminate_playbook"], group, vm_name, vm_ip)
            except Exception:
                # ignore all errors
                raise
        log.exception("Error during ansible invocation: %s", err.msg)
        return
    except Exception as err:
        log.exception("[Unexpected] Failed to spawn builder: %s", err)
        return

    spawn_result["group"] = group
    spawn_result["topic"] = EventTopics.VM_SPAWNED
    try:
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(spawn_result))
    except Exception as err:
        log.exception("Failed to publish msg about new VM: %s with error: %s",
                      spawn_result, err)


class Spawner(Executor):
    __name_for_log__ = "spawner"
    __who_for_log__ = "spawner"

    def __init__(self, *args, **kwargs):
        super(Spawner, self).__init__(*args, **kwargs)
        self.proc_to_group = {}  # {proc: Thread -> group: int}

    def after_proc_finished(self, proc):
        self.proc_to_group.pop(proc)

    def get_proc_num_per_group(self, group):
        return sum(1 for _, gr in self.proc_to_group.items() if gr == group)

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

        proc = self.run_detached(do_spawn_and_publish, args=(self.opts, spawn_playbook, group))
        self.proc_to_group[proc] = group
