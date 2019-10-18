# coding: utf-8
import json
#from setproctitle import setproctitle
# from multiprocessing import Process
#from threading import Thread

from backend.helpers import get_redis_connection
from backend.vm_manage import PUBSUB_MB, EventTopics
from backend.vm_manage.executor import Executor

from ..helpers import get_redis_logger
from ..sshcmd import SSHConnection


def check_health(opts, vm_name, vm_ip):
    """
    Test connectivity to the VM

    :param vm_ip: ip address to the newly created VM
    :raises: :py:class:`~backend.exceptions.CoprWorkerSpawnFailError`: validation fails
    """
    log = get_redis_logger(opts, "vmm.check_health.detached", "vmm")

    result = {
        "vm_ip": vm_ip,
        "vm_name": vm_name,
        "msg": "",
        "result": "OK",
        "topic": EventTopics.HEALTH_CHECK
    }

    err_msg = None
    try:
        conn = SSHConnection(opts.build_user or "root", vm_ip, config_file=opts.ssh.builder_config)
        rc, stdout, _ = conn.run_expensive("echo hello")
        if rc != 0 or stdout != "hello\n":
            err_msg = "Unexpected check output"
    except Exception as error:
        err_msg = "Healtcheck failed for VM {} with error {}".format(vm_ip, error)
        log.exception(err_msg)

    try:
        if err_msg:
            result["result"] = "failed"
            result["msg"] = err_msg
        rc = get_redis_connection(opts)
        rc.publish(PUBSUB_MB, json.dumps(result))
    except Exception as err:
        log.exception("Failed to publish msg health check result: %s with error: %s",
                      result, err)


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
