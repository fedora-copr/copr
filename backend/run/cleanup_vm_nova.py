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
from novaclient.v1_1.client import Client

sys.path.append("/usr/share/copr/")

try:
    from backend.helpers import utc_now
except ImportError:
    # TODO: remove when updated version of copr-backend will be released
    import pytz

    def utc_now():
        """
        :return datetime.datetime: Current utc datetime with specified timezone
        """
        u = datetime.utcnow()
        u = u.replace(tzinfo=pytz.utc)
        return u


logging.getLogger("requests").setLevel(logging.ERROR)


nova_cloud_vars_path = os.environ.get("NOVA_CLOUD_VARS", "/home/copr/provision/nova_cloud_vars.yml")


def read_config():
    with open(nova_cloud_vars_path) as handle:
        conf = yaml.load(handle.read())
    return conf


def get_client(conf):
    return Client(username=conf["OS_USERNAME"],
                  api_key=conf["OS_PASSWORD"],
                  project_id=conf["OS_TENANT_NAME"],
                  auth_url=conf["OS_AUTH_URL"],
                  insecure=True)


class Cleaner(object):
    def __init__(self, conf):
        self.conf = conf
        self.nt = None
        self.ps_set = None

    def post_init(self):
        self.nt = get_client(self.conf)
        # TODO: use VM management after release
        self.ps_set = "\n".join(p.name + " ".join(p.cmdline) for p in psutil.process_iter())
        # log.debug("ps_set: \n{}".format(self.ps_set))

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
        # log.debug("Server {} created {} now {}; delta: {}".format(srv, dt_created, utc_now(), delta))
        return delta > 60 * 10  # 10 minutes

    def check_one(self, srv_id):
        srv = self.nt.servers.get(srv_id)
        log.debug("checking vm: {}".format(srv))
        srv.get()
        if srv.status == u"ERROR":
            log.info("server {} got into the error state, deleting".format(srv))
            self.terminate(srv)
        elif self.old_enough(srv) and srv.human_id not in self.ps_set:
            log.info("server {} not used by any builder".format(srv))
            self.terminate(srv)
        # elif not self.old_enough(srv):
        #     log.info("Server {} not old enough".format(srv))

    def main(self):
        """
        Terminate erred VM's and VM's with uptime > 10 minutes and which doesn't have associated process
        """
        self.post_init()
        start = time.time()

        srv_list = self.nt.servers.list(detailed=False)
        with ThreadPoolExecutor(max_workers=20) as executor:
            future_check = {executor.submit(self.check_one, srv.id): srv.id for srv in srv_list}
            for future in as_completed(future_check):
                try:
                    future.result()
                except Exception as exc:
                    log.exception(exc)

        log.info("cleanup consumed: {} seconds".format(time.time() - start))

if __name__ == "__main__":
    logging.basicConfig(
        filename="/var/log/copr/cleanup_vms.log",
        # filename="/tmp/cleanup_vms.log",
        # stream=sys.stdout,
        format='[%(asctime)s][%(thread)s][%(levelname)6s]: %(message)s',
        level=logging.INFO)

    log = logging.getLogger(__name__)
    log.info("Logger done")

    cleaner = Cleaner(read_config())
    cleaner.main()
