#!/usr/bin/python -ttu


from backend import errors
from backend.dispatcher import Worker
from backend.actions import Action
from bunch import Bunch
from retask.task import Task
from retask.queue import Queue
import ConfigParser
import daemon
import glob
import grp
import json
import lockfile
import logging
import multiprocessing
import optparse
import os
import pwd
import requests
import setproctitle
import signal
import sys
import time


def _get_conf(cp, section, option, default):
    """
    To make returning items from config parser less irritating
    """

    if cp.has_section(section) and cp.has_option(section, option):
        return cp.get(section, option)
    return default


class CoprJobGrab(multiprocessing.Process):

    """
    Fetch jobs from the Frontend
    - submit them to the jobs queue for workers
    """

    def __init__(self, opts, events, jobs, lock):
        # base class initialization
        multiprocessing.Process.__init__(self, name="jobgrab")

        self.opts = opts
        self.events = events
        self.jobs = jobs
        self.added_jobs = []
        self.lock = lock

    def event(self, what):
        self.events.put({"when": time.time(), "who": "jobgrab", "what": what})

    def fetch_jobs(self):
        try:
            r = requests.get(
                "{0}/waiting/".format(self.opts.frontend_url),
                auth=("user", self.opts.frontend_auth))

        except requests.RequestException as e:
            self.event("Error retrieving jobs from {0}: {1}".format(
                       self.opts.frontend_url, e))
        else:
            try:
                r_json = json.loads(r.content)  # using old requests on el6 :(
            except ValueError as e:
                self.event("Error getting JSON build list from FE {0}"
                           .format(e))
                return

            if "builds" in r_json and r_json["builds"]:
                self.event("{0} jobs returned".format(len(r_json["builds"])))
                count = 0
                for b in r_json["builds"]:
                    if "id" in b:
                        extended_id = "{0}-{1}".format(b["id"], b["chroot"])
                        jobfile = os.path.join(
                            self.opts.jobsdir,
                            "{0}.json".format(extended_id))

                        if (not os.path.exists(jobfile) and
                                extended_id not in self.added_jobs):

                            count += 1
                            open(jobfile, 'w').write(json.dumps(b))
                            self.event("Wrote job: {0}".format(extended_id))
                if count:
                    self.event("New jobs: %s" % count)
            if "actions" in r_json and r_json["actions"]:
                self.event("{0} actions returned".format(
                    len(r_json["actions"])))

                for action in r_json["actions"]:
                    ao = Action(self.opts, self.events, action, self.lock)
                    ao.run()

    def run(self):
        setproctitle.setproctitle("CoprJobGrab")
        abort = False
        try:
            while not abort:
                self.fetch_jobs()
                for f in sorted(glob.glob(
                        os.path.join(self.opts.jobsdir, "*.json"))):

                    n = os.path.basename(f).replace(".json", "")
                    if n not in self.added_jobs:
                        self.jobs.put(f)
                        self.added_jobs.append(n)
                        self.event("adding to work queue id {0}".format(n))
                time.sleep(self.opts.sleeptime)
        except KeyboardInterrupt:
            return


class CoprLog(multiprocessing.Process):

    """log mechanism where items from the events queue get recorded"""

    def __init__(self, opts, events):

        # base class initialization
        multiprocessing.Process.__init__(self, name="logger")

        self.opts = opts
        self.events = events

        logdir = os.path.dirname(self.opts.logfile)
        if not os.path.exists(logdir):
            os.makedirs(logdir, mode=0750)

        # setup a log file to write to
        logging.basicConfig(filename=self.opts.logfile, level=logging.DEBUG)

    def log(self, event):

        when = time.strftime("%F %T", time.gmtime(event["when"]))
        msg = "{0} : {1}: {2}".format(when,
                                      event["who"],
                                      event["what"].strip())

        try:
            if self.opts.verbose:
                sys.stderr.write("{0}\n".format(msg))
                sys.stderr.flush()
            logging.debug(msg)
        except (IOError, OSError) as e:
            sys.stderr.write("Could not write to logfile {0} - {1}\n".format(
                self.logfile, e))

    # event format is a dict {when:time, who:[worker|logger|job|main],
    # what:str}
    def run(self):
        setproctitle.setproctitle("CoprLog")
        abort = False
        try:
            while not abort:
                e = self.events.get()
                if "when" in e and "who" in e and "what" in e:
                    self.log(e)
        except KeyboardInterrupt:
            return


class CoprBackend(object):

    """
    Core process - starts/stops/initializes workers
    """

    def __init__(self, config_file=None, ext_opts=None):
        # read in config file
        # put all the config items into a single self.opts bunch

        if not config_file:
            raise errors.CoprBackendError("Must specify config_file")

        self.config_file = config_file
        self.ext_opts = ext_opts  # to stow our cli options for read_conf()
        self.opts = self.read_conf()
        self.lock = multiprocessing.Lock()

        # job is a path to a jobfile on the localfs
        self.jobs = multiprocessing.Queue()
        self.events = multiprocessing.Queue()
        # event format is a dict {when:time, who:[worker|logger|job|main],
        # what:str}

        # create logger
        self._logger = CoprLog(self.opts, self.events)
        self._logger.start()

        self.event("Starting up Job Grabber")
        # create job grabber
        self._jobgrab = CoprJobGrab(self.opts, self.events, self.jobs, self.lock)
        self._jobgrab.start()
        self.worker_num = 0
        self.abort = False

        if not os.path.exists(self.opts.worker_logdir):
            os.makedirs(self.opts.worker_logdir, mode=0750)

        self.workers = []

    def event(self, what):
        self.events.put({"when": time.time(), "who": "main", "what": what})

    def read_conf(self):
        "read in config file - return Bunch of config data"
        opts = Bunch()
        cp = ConfigParser.ConfigParser()
        try:
            cp.read(self.config_file)
            opts.results_baseurl = _get_conf(
                cp, "backend", "results_baseurl", "http://copr")
            opts.frontend_url = _get_conf(
                cp, "backend", "frontend_url", "http://coprs/rest/api")
            opts.frontend_auth = _get_conf(
                cp, "backend", "frontend_auth", "PASSWORDHERE")

            opts.architectures = _get_conf(
                cp, "backend", "architectures", "i386,x86_64").split(",")

            opts.spawn_playbook = {}
            for arch in opts.architectures:
                opts.spawn_playbook[arch] = _get_conf(
                    cp, "backend", "spawn_playbook-{0}".format(arch),
                    "/srv/copr-work/provision/builderpb-{0}.yml".format(arch))

            opts.terminate_playbook = _get_conf(
                cp, "backend", "terminate_playbook",
                "/srv/copr-work/provision/terminatepb.yml")

            opts.jobsdir = _get_conf(cp, "backend", "jobsdir", None)
            opts.destdir = _get_conf(cp, "backend", "destdir", None)
            opts.exit_on_worker = _get_conf(
                cp, "backend", "exit_on_worker", False)
            opts.fedmsg_enabled = _get_conf(
                cp, "backend", "fedmsg_enabled", False)
            opts.sleeptime = int(_get_conf(cp, "backend", "sleeptime", 10))
            opts.num_workers = int(_get_conf(cp, "backend", "num_workers", 8))
            opts.timeout = int(_get_conf(cp, "builder", "timeout", 1800))
            opts.logfile = _get_conf(
                cp, "backend", "logfile", "/var/log/copr/backend.log")
            opts.verbose = _get_conf(cp, "backend", "verbose", False)
            opts.worker_logdir = _get_conf(
                cp, "backend", "worker_logdir", "/var/log/copr/workers/")
            opts.spawn_vars = _get_conf(cp, "backend", "spawn_vars", None)
            opts.terminate_vars = _get_conf(cp, "backend", "terminate_vars",
                None)

            # thoughts for later
            # ssh key for connecting to builders?
            # cloud key stuff?
            #
        except ConfigParser.Error as e:
            raise errors.CoprBackendError(
                "Error parsing config file: {0}: {1}".format(
                    self.config_file, e))

        if not opts.jobsdir or not opts.destdir:
            raise errors.CoprBackendError(
                "Incomplete Config - must specify"
                " jobsdir and destdir in configuration")

        if self.ext_opts:
            for v in self.ext_opts:
                setattr(opts, v, self.ext_opts.get(v))
        return opts

    def run(self):
        self.abort = False
        while not self.abort:
            # re-read config into opts
            self.opts = self.read_conf()

            if self.jobs.qsize():
                self.event("# jobs in queue: {0}".format(self.jobs.qsize()))
                # this handles starting/growing the number of workers
                if len(self.workers) < self.opts.num_workers:
                    self.event("Spinning up more workers for jobs")
                    for _ in range(self.opts.num_workers - len(self.workers)):
                        self.worker_num += 1
                        w = Worker(
                            self.opts, self.jobs, self.events, self.worker_num,
                            lock=self.lock)
                        self.workers.append(w)
                        w.start()
                    self.event("Finished starting worker processes")
                # FIXME - prune out workers
                # if len(self.workers) > self.opts.num_workers:
                #    killnum = len(self.workers) - self.opts.num_workers
                #    for w in self.workers[:killnum]:
                # insert a poison pill? Kill after something? I dunno.
                # FIXME - if a worker bombs out - we need to check them
                # and startup a new one if it happens
            # check for dead workers and abort
            for w in self.workers:
                if not w.is_alive():
                    self.event("Worker {0} died unexpectedly".format(
                        w.worker_num))
                    if self.opts.exit_on_worker:
                        raise errors.CoprBackendError(
                            "Worker died unexpectedly, exiting")
                    else:
                        self.workers.remove(w)  # it is not working anymore
                        w.terminate()  # kill it with a fire

            time.sleep(self.opts.sleeptime)

    def terminate(self):
        """
        Cleanup backend processes (just workers for now)
        """

        self.abort = True
        for w in self.workers:
            self.workers.remove(w)
            w.terminate()


def parse_args(args):
    parser = optparse.OptionParser("\ncopr-be [options]")
    parser.add_option("-c", "--config", default="/etc/copr/copr-be.conf",
                      dest="config_file",
                      help="config file to use for copr-be run")
    parser.add_option("-d", "--daemonize", default=False, dest="daemonize",
                      action="store_true", help="daemonize or not")
    parser.add_option("-p", "--pidfile",
                      default="/var/run/copr-backend/copr-be.pid",
                      dest="pidfile",
                      help="pid file to use for copr-be if daemonized")
    parser.add_option("-x", "--exit", default=False, dest="exit_on_worker",
                      action="store_true", help="exit on worker failure")
    parser.add_option("-v", "--verbose", default=False, dest="verbose",
                      action="store_true", help="be more verbose")

    opts, args = parser.parse_args(args)
    if not os.path.exists(opts.config_file):
        sys.stderr.write("No config file found at: {0}\n".format(
            opts.config_file))
        sys.exit(1)
    opts.config_file = os.path.abspath(opts.config_file)

    ret_opts = Bunch()
    for o in ("daemonize", "exit_on_worker", "pidfile", "config_file"):
        setattr(ret_opts, o, getattr(opts, o))

    return ret_opts


def main(args):
    opts = parse_args(args)

    try:
        context = daemon.DaemonContext(
            pidfile=lockfile.FileLock(opts.pidfile),
            gid=grp.getgrnam("copr").gr_gid,
            uid=pwd.getpwnam("copr").pw_uid,
            detach_process=opts.daemonize,
            umask=022,
            stderr=sys.stderr,
            signal_map={
                signal.SIGTERM: "terminate",
                signal.SIGHUP: "terminate",
            },
        )
        with context:
            cbe = CoprBackend(opts.config_file, ext_opts=opts)
            cbe.run()
    except (Exception, KeyboardInterrupt):
        sys.stderr.write("Killing/Dying\n")
        if "cbe" in locals():
            cbe.terminate()
        raise

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.stderr.write("\nUser cancelled, may need cleanup\n")
        sys.exit(0)
