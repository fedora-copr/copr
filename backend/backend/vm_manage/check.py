# coding: utf-8
import json
from setproctitle import setproctitle
import time
from multiprocessing import Process
import sys

from ansible.runner import Runner

from backend.helpers import get_redis_connection, format_tb
from backend.vm_manage import PUBSUB_MB, EventTopics
from backend.vm_manage.executor import Executor


def check_health(opts, events, vm_name, vm_ip):
    """
    Test connectivity to the VM

    :param vm_ip: ip address to the newly created VM
    :raises: :py:class:`~backend.exceptions.CoprWorkerSpawnFailError`: validation fails
    """
    setproctitle("check VM: {}".format(vm_ip))

    def log_fn(msg):
        events.put({"when": time.time(), "who": "checker", "what": msg})

    runner_options = dict(
        remote_user="root",
        host_list="{},".format(vm_ip),
        pattern=vm_ip,
        forks=1,
        transport=opts.ssh.transport,
        timeout=10
    )
    connection = Runner(**runner_options)
    connection.module_name = "shell"
    connection.module_args = "echo hello"

    result = {
        "vm_ip": vm_ip,
        "vm_name": vm_name,
        "msg": "",
        "result": "OK",
        "topic": EventTopics.HEALTH_CHECK
    }
    err_msg = None
    try:
        res = connection.run()
        if vm_ip not in res.get("contacted", {}):
            err_msg = (
                "VM is not responding to the testing playbook."
                "Runner options: {}".format(runner_options) +
                "Ansible raw response:\n{}".format(res))

    except Exception as exception:
        _, _, ex_tb = sys.exc_info()
        err_msg = (
            "Failed to check  VM ({})"
            "due to ansible error: {}; {}".format(vm_ip, exception, format_tb(exception, ex_tb)))

    try:
        if err_msg:
            result["result"] = "failed"
            result["msg"] = err_msg
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(result))
    except Exception as err:
        log_fn("Failed to publish msg health check result: {} with error: {}"
               .format(result, err))


class HealthChecker(Executor):

    __name_for_log__ = "health_checker"

    def run_check_health(self, vm_name, vm_ip):
        self.recycle()

        proc = Process(target=check_health, args=(self.opts, self.events, vm_name, vm_ip))
        self.child_processes.append(proc)
        proc.start()
        self.log("Check health process started: {}".format(proc.pid))
