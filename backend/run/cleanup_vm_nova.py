#!/usr/bin/python
# coding: utf-8

import os
import sys
import time
import logging

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dateutil.parser import parse as dt_parse

import psutil
import yaml
from novaclient.client import Client

sys.path.append("/usr/share/copr/")

from backend.helpers import BackendConfigReader
from backend.helpers import utc_now

try:
    from backend.vm_manage.manager import VmManager
except ImportError:
    VmManager = None

logging.getLogger("requests").setLevel(logging.ERROR)


nova_cloud_vars_path = os.environ.get("NOVA_CLOUD_VARS", "/home/copr/provision/nova_cloud_vars.yml")


def read_config():
    with open(nova_cloud_vars_path) as handle:
        conf = yaml.load(handle.read())
    return conf


def get_client(conf):
    username = conf["OS_USERNAME"]
    password = conf["OS_PASSWORD"]
    tenant_name = conf["OS_TENANT_NAME"]
    auth_url = conf["OS_AUTH_URL"]
    return Client('2', username, password, tenant_name, auth_url)


def get_managed_vms_names():
    result = []
    if VmManager:
        opts = BackendConfigReader().read()
        vmm = VmManager(opts, log)
        result.extend(vmd.vm_name.lower() for vmd in vmm.get_all_vm())
    return result


class Cleaner(object):
    def __init__(self, conf):
        self.conf = conf
        self.nt = None

    @staticmethod
    def terminate(srv):
        try:
            srv.delete()
            log.info("delete invoked for: {}".format(srv))
        except Exception as err:
            log.exception("failed to request VM termination: {}".format(err))

    @staticmethod
    def old_enough(srv):
        dt_created = dt_parse(srv.created)
        delta = (utc_now() - dt_created).total_seconds()
        # log.info("Server {} created {} now {}; delta: {}".format(srv, dt_created, utc_now(), delta))
        return delta > 60 * 5  # 5 minutes

    def check_one(self, srv_id, vms_names):
        srv = self.nt.servers.get(srv_id)
        log.info("checking vm: {}".format(srv))
        srv.get()
        if srv.status.lower().strip() == "error":
            log.info("server {} got into the error state, terminating".format(srv))
            self.terminate(srv)
        elif self.old_enough(srv) and srv.human_id.lower() not in vms_names:
            log.info("server {} not placed in our db, terminating".format(srv))
            self.terminate(srv)

    def main(self):
        """
        Terminate erred VM's and VM's with uptime > 10 minutes and which doesn't have associated process
        """
        start = time.time()
        log.info("Cleanup start")

        self.nt = get_client(self.conf)
        srv_list = self.nt.servers.list(detailed=False)
        vms_names = get_managed_vms_names()
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_check = {executor.submit(self.check_one, srv.id, vms_names): srv.id for srv in srv_list}
            for future in as_completed(future_check):
                try:
                    future.result()
                except Exception as exc:
                    log.exception(exc)

        log.info("cleanup consumed: {} seconds".format(time.time() - start))

if __name__ == "__main__":
    logging.basicConfig(
        filename="/var/log/copr-backend/cleanup_vms.log",
        # filename="/tmp/cleanup_vms.log",
        # stream=sys.stdout,
        format='[%(asctime)s][%(thread)s][%(levelname)6s]: %(message)s',
        level=logging.INFO)

    log = logging.getLogger(__name__)

    cleaner = Cleaner(read_config())
    cleaner.main()
