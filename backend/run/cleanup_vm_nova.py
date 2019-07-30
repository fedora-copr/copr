#!/usr/bin/python3
# coding: utf-8

import os
import sys
import time
import logging
import argparse

from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from dateutil.parser import parse as dt_parse

import yaml
from novaclient.client import Client

# don't kill younger VMs than this (minutes)
SPAWN_TIMEOUT = 10

sys.path.append("/usr/share/copr/")

from backend.helpers import BackendConfigReader
from backend.helpers import utc_now

try:
    from backend.vm_manage.manager import VmManager
    from backend.vm_manage import VmStates
except ImportError:
    VmManager = None

logging.getLogger("requests").setLevel(logging.ERROR)

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)
log_format = logging.Formatter('[%(asctime)s][%(thread)s][%(levelname)6s]: %(message)s')
hfile = logging.FileHandler('/var/log/copr-backend/cleanup_vms.log')
hfile.setLevel(logging.INFO)
hstderr = logging.StreamHandler()
hfile.setFormatter(log_format)
log.addHandler(hfile)
log.addHandler(hstderr)


nova_cloud_vars_path = os.environ.get("NOVA_CLOUD_VARS", "/home/copr/provision/nova_cloud_vars.yml")


def get_arg_parser():
    parser = argparse.ArgumentParser(
        description="Delete all errored or copr-managed VMs from relevant "
                    "OpenStack tenant",
    )

    parser.add_argument('--kill-also-unused', action='store_true',
                        help='Delete also tracked, but unused VMs',
                        default=False)
    return parser


def read_config():
    with open(nova_cloud_vars_path) as handle:
        conf = yaml.safe_load(handle.read())
    return conf


def get_client(conf):
    username = conf["OS_USERNAME"]
    password = conf["OS_PASSWORD"]
    tenant_name = conf["OS_TENANT_NAME"]
    auth_url = conf["OS_AUTH_URL"]
    return Client('2', username, password, tenant_name, auth_url)


def get_managed_vms():
    result = {}
    if VmManager:
        opts = BackendConfigReader().read()
        vmm = VmManager(opts, log)
        for vmd in vmm.get_all_vm():
            result[vmd.vm_name.lower()] = {
                'unused': vmd.state == VmStates.READY,
            }
    return result


class Cleaner(object):
    def __init__(self, conf):
        self.conf = conf
        self.nt = None

    @staticmethod
    def terminate(srv):
        try:
            srv.delete()
        except Exception:
            log.exception("failed to request VM termination")

    @staticmethod
    def old_enough(srv):
        dt_created = dt_parse(srv.created)
        delta = (utc_now() - dt_created).total_seconds()
        if delta > 60 * SPAWN_TIMEOUT:
            log.debug("Server '%s', created: %s, now: %s, delta: %s",
                      srv.name, dt_created, utc_now(), delta)
            return True
        return False

    def check_one(self, srv_id, managed_vms, opts):
        srv = self.nt.servers.get(srv_id)
        log.debug("checking vm '%s'", srv.name)
        srv.get()

        managed = managed_vms.get(srv.human_id.lower())

        if srv.status.lower().strip() == "error":
            log.info("vm '%s' got into the error state, terminating", srv.name)
            self.terminate(srv)
        elif not managed:
            if self.old_enough(srv): # give the spawner some time
                log.info("vm '%s' not placed in our db, terminating", srv.name)
                self.terminate(srv)
        elif opts.kill_also_unused and managed['unused']:
            log.info("terminating unused vm %s", srv.name)
            self.terminate(srv)


    def main(self, opts):
        """
        Terminate
        - errored VM's and
        - VM's with uptime > SPAWN_TIMEOUT minutes and which don't have entry in
          redis DB
        - when --kill-also-unused, we also terminate ready VMs
        """
        start = time.time()
        log.info("Cleanup start")

        self.nt = get_client(self.conf)
        srv_list = self.nt.servers.list(detailed=False)
        managed_vms = get_managed_vms()
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_check = {
                executor.submit(self.check_one, srv.id, managed_vms, opts):
                srv.id for srv in srv_list
            }
            for future in as_completed(future_check):
                try:
                    future.result()
                except Exception as exc:
                    log.exception(exc)

        log.info("cleanup consumed: %s seconds", time.time() - start)


if __name__ == "__main__":
    cleaner = Cleaner(read_config())
    cleaner.main(get_arg_parser().parse_args())
