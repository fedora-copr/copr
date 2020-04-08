#!/usr/bin/python3
# coding: utf-8

from setproctitle import setproctitle

from copr_backend.vm_manage.manager import VmManager
from copr_backend.vm_manage.spawn import Spawner
from copr_backend.vm_manage.event_handle import EventHandler
from copr_backend.vm_manage.terminate import Terminator
from copr_backend.vm_manage.check import HealthChecker
from copr_backend.daemons.vm_master import VmMaster
from copr_backend.helpers import get_redis_logger, get_backend_opts


class VmmRunner(object):

    def __init__(self, opts):
        self.opts = opts
        self.log = get_redis_logger(self.opts, "vmm.main", "vmm")

    def run(self):
        # todo: 1) do all ansible calls through subprocess
        # 2) move to Python 3 and asyncIO all in one thread + executors
        # ... -> eliminate multiprocessing here,
        # ... possible to use simple logging, with redis handler

        self.log.info("Creating VM Spawner, HealthChecker, Terminator")
        self.spawner = Spawner(self.opts)
        self.checker = HealthChecker(self.opts)
        self.terminator = Terminator(self.opts)
        self.vm_manager = VmManager(
            opts=self.opts, logger=self.log,
        )
        self.log.info("Starting up VM EventHandler")
        self.event_handler = EventHandler(self.opts,
                                          vmm=self.vm_manager,
                                          terminator=self.terminator)
        self.event_handler.post_init()
        self.event_handler.start()

        self.log.info("Starting up VM Master")
        self.vm_master = VmMaster(self.opts,
                                  vmm=self.vm_manager,
                                  spawner=self.spawner,
                                  checker=self.checker)
        self.vm_master.start()
        setproctitle("Copr VMM base process")


def main():
    opts = get_backend_opts()
    vr = VmmRunner(opts)
    vr.run()

if __name__ == "__main__":
    main()
