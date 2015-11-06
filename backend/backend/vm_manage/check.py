# coding: utf-8
import json
#from setproctitle import setproctitle
import time
# from multiprocessing import Process
#from threading import Thread

from ansible.runner import Runner

from backend.helpers import get_redis_connection
from backend.vm_manage import PUBSUB_MB, EventTopics
from backend.vm_manage.executor import Executor

from ..helpers import get_redis_logger


def check_health(opts, vm_name, vm_ip):
    """
    Test connectivity to the VM

    :param vm_ip: ip address to the newly created VM
    :raises: :py:class:`~backend.exceptions.CoprWorkerSpawnFailError`: validation fails
    """
    # setproctitle("check VM: {}".format(vm_ip))

    log = get_redis_logger(opts, "vmm.check_health.detached", "vmm")

    runner_options = dict(
        remote_user=opts.build_user or "root",
        host_list="{},".format(vm_ip),
        pattern=vm_ip,
        forks=1,
        transport=opts.ssh.transport,
        timeout=opts.vm_ssh_check_timeout
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

    except Exception as error:
        err_msg = "Failed to check  VM ({})due to ansible error: {}".format(vm_ip, error)
        log.exception(err_msg)

    try:
        if err_msg:
            result["result"] = "failed"
            result["msg"] = err_msg
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(result))
    except Exception as err:
        log.exception("Failed to publish msg health check result: {} with error: {}"
                      .format(result, err))


class HealthChecker(Executor):

    __name_for_log__ = "health_checker"
    __who_for_log__ = "vmm"

    def run_check_health(self, vm_name, vm_ip):
        self.recycle()
        self.run_detached(check_health, args=(self.opts, vm_name, vm_ip))
        # proc = Process(target=check_health, args=(self.opts, vm_name, vm_ip))
        # proc = Thread(target=check_health, args=(self.opts, vm_name, vm_ip))
        # self.child_processes.append(proc)
        # proc.start()
        # self.log.debug("Check health process started: {}".format(proc.pid))
