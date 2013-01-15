#!/usr/bin/python -tt


import sys
import os
import glob
import time
import multiprocessing
from backend.dispatcher import Worker
from backend import errors
from bunch import Bunch
import ConfigParser
import optparse
import json
import requests

def _get_conf(cp, section, option, default):
    """to make returning items from config parser less irritating"""
    if cp.has_section(section) and cp.has_option(section,option):
        return cp.get(section, option)
    return default



class CoprJobGrab(multiprocessing.Process):
    """Fetch jobs from the Frontend - submit them to the jobs queue for workers"""

    def __init__(self, opts, events, jobs):
        # base class initialization
        multiprocessing.Process.__init__(self, name="jobgrab")

        self.opts = opts
        self.events = events
        self.jobs = jobs
        self.added_jobs = []

    def event(self, what):
        self.events.put({'when':time.time(), 'who':'job', 'what':what})
        
    def fetch_jobs(self):
        self.event('fetching jobs')
        try:
            r = requests.get('%s/waiting_builds/' % self.opts.frontend_url) # auth stuff here? maybe/maybenot
        except requests.RequestException, e:
            self.event('Error retrieving jobs from %s: %s' % (self.opts.frontend_url, e))
        else:
            try:
                r_json = json.loads(r.content) # using old requests on el6 :(
            except ValueError, e:
                self.event('Error getting JSON build list from FE %s' % e)
                return
            
            if 'builds' in r_json and r_json['builds']:
                self.event('%s jobs returned' % len(r_json['builds']))
                count = 0
                for b in r_json['builds']:
                    if 'id' in b:
                        jobfile = self.opts.jobsdir + '/%s.json' % b['id']
                        if not os.path.exists(jobfile) and b['id'] not in self.added_jobs:
                            count += 1
                            open(jobfile, 'w').write(json.dumps(b))
                            self.event('Wrote job: %s' % b['id'])
                if count:
                    self.event('New jobs: %s' % count)

    def run(self):
        abort = False
        while not abort:
            self.fetch_jobs()
            for f in sorted(glob.glob(self.opts.jobsdir + '/*.json')):
                n = os.path.basename(f).replace('.json', '')
                if n not in self.added_jobs:
                    self.jobs.put(f)
                    self.added_jobs.append(n)
                    self.event('adding to work queue id %s' % n)

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

        if not os.path.exists(self.opts.destdir):
            os.makedirs(self.opts.destdir, mode=0755)

        # setup a log file to write to
        self.logfile = self.opts.logfile
    
    def log(self, event):
        
        when =  time.strftime('%F %T', time.gmtime(event['when']))
        msg = '%s : %s %s' % (when, event['who'], event['what'].strip())
            
        try:
            open(self.logfile, 'a').write(msg + '\n')
        except (IOError, OSError), e:
            print >>sys.stderr, 'Could not write to logfile %s - %s' % (self.logfile, str(e))


    # event format is a dict {when:time, who:[worker|logger|job|main], what:str}
    def run(self):
        abort = False
        while not abort:
            for e in self.events.get():
                if 'when' in e and 'who' in e and 'what' in e:
                    self.log(e)

class CoprBackend(object):
    """core process - starts/stops/initializes workers"""
    
    def __init__(self, config_file=None, ext_opts=None):
        # read in config file
        # put all the config items into a single self.opts bunch
        
        if not config_file:
            raise errors.CoprBackendError, "Must specify config_file"
        
        self.config_file = config_file
        self.ext_opts = ext_opts # to stow our cli options for read_conf()
        self.opts = self.read_conf()
        
        self.jobs = multiprocessing.Queue() # job is a path to a jobfile on the localfs
        self.events = multiprocessing.Queue()
        # event format is a dict {when:time, who:[worker|logger|job|main], what:str}


        # create logger
        self._logger = CoprLog(self.opts, self.events)
        self._logger.start()
        
        self.event('Starting up Job Grabber')
        # create job grabber
        self._jobgrab = CoprJobGrab(self.opts, self.events, self.jobs)
        self._jobgrab.start()

        if not os.path.exists(self.opts.worker_logdir):
            os.makedirs(self.opts.worker_logdir, mode=0750)
        
        self.workers = []
        self.added_jobs = []

    def event(self, what):
        self.events.put({'when':time.time(), 'who':'main', 'what':what})
        
    def read_conf(self):
        "read in config file - return Bunch of config data"
        opts = Bunch()
        cp = ConfigParser.ConfigParser()
        try:
            cp.read(self.config_file)
            opts.results_baseurl = _get_conf(cp,'backend', 'results_baseurl', 'http://copr')
            opts.frontend_url = _get_conf(cp, 'backend', 'frontend_url', 'http://coprs/rest/api')
            opts.frontend_auth = _get_conf(cp,'backend', 'frontend_auth', 'PASSWORDHERE')
            opts.spawn_playbook = _get_conf(cp,'backend','spawn_playbook', '/etc/copr/builder_playbook.yml')
            opts.terminate_playbook = _get_conf(cp,'backend','terminate_playbook', '/etc/copr/terminate_playbook.yml')
            opts.jobsdir = _get_conf(cp, 'backend', 'jobsdir', None)
            opts.destdir = _get_conf(cp, 'backend', 'destdir', None)
            opts.daemonize = _get_conf(cp, 'backend', 'daemonize', True)
            opts.exit_on_worker = _get_conf(cp, 'backend', 'exit_on_worker', False)
            opts.sleeptime = int(_get_conf(cp, 'backend', 'sleeptime', 10))
            opts.num_workers = int(_get_conf(cp, 'backend', 'num_workers', 8))
            opts.timeout = int(_get_conf(cp, 'builder', 'timeout', 1800))
            opts.logfile = _get_conf(cp, 'backend', 'logfile', '/var/log/copr/backend.log')
            opts.worker_logdir = _get_conf(cp, 'backend', 'worker_logdir', '/var/log/copr/worker/')
            # thoughts for later
            # ssh key for connecting to builders?
            # cloud key stuff?
            # 
        except ConfigParser.Error, e:
            raise errors.CoprBackendError, 'Error parsing config file: %s: %s' % (self.config_file, e)
        
        
        if not opts.jobsdir or not opts.destdir:
            raise errors.CoprBackendError, "Incomplete Config - must specify jobsdir and destdir in configuration"
            
        if self.ext_opts:
            for v in self.ext_opts:
                setattr(opts, v, self.ext_opts.get(v))
        return opts
        
        
    
    def run(self):

        abort = False
        while not abort:
            # re-read config into opts
            self.opts = self.read_conf()
            
            if self.jobs.qsize():
                self.event("# jobs in queue: %s" % self.jobs.qsize())
                # this handles starting/growing the number of workers
                if len(self.workers) < self.opts.num_workers:
                    self.event("Spinning up more workers for jobs")
                    for i in range(self.opts.num_workers - len(self.workers)):
                        worker_num = len(self.workers) + 1
                        w = Worker(self.opts, self.jobs, self.events, worker_num)
                        self.workers.append(w)
                        w.start()
                    self.event("Finished starting worker processes")
                # FIXME - prune out workers
                #if len(self.workers) > self.opts.num_workers:
                #    killnum = len(self.workers) - self.opts.num_workers
                #    for w in self.workers[:killnum]:
                #       #insert a poison pill? Kill after something? I dunno.
                # FIXME - if a worker bombs out - we need to check them
                # and startup a new one if it happens
            # check for dead workers and abort
            for w in self.workers:
                if not w.is_alive():
                    self.event('Worker %d died unexpectedly' % w.worker_num)
                    if self.opts.exit_on_worker:
                        raise errors.CoprBackendError, "Worker died unexpectedly, exiting"
                    else:
                        self.workers.remove(w) # it is not working anymore
                        w.terminate() # kill it with a fire

            time.sleep(self.opts.sleeptime)

# lifted from certmaster
def daemonize(pidfile=None): 
    """
    Daemonize this process with the UNIX double-fork trick.
    Writes the new PID to the provided file name if not None.
    """

    cur_umask = os.umask(077)
    os.umask(cur_umask)
    
    pid = os.fork()
    if pid > 0:
        sys.exit(0)
    os.chdir("/")
    os.setsid()
    os.umask(cur_umask)
    pid = os.fork()

    os.close(0)
    os.close(1)
    os.close(2)

    # The standard I/O file descriptors are redirected to /dev/null by default.
    if (hasattr(os, "devnull")):  
        REDIRECT_TO = os.devnull
    else:
        REDIRECT_TO = "/dev/null"

    # based on http://code.activestate.com/recipes/278731/
    os.open(REDIRECT_TO, os.O_RDWR)     # standard input (0)

    os.dup2(0, 1)                       # standard output (1)
    os.dup2(0, 2)                       # standard error (2)



    if pid > 0:
        if pidfile is not None:
            open(pidfile, "w").write(str(pid))
        sys.exit(0)

def parse_args(args):
    parser = optparse.OptionParser('\ncopr-be [options]')
    parser.add_option('-c', '--config', default='/etc/copr-be.conf', dest='config_file',
            help="config file to use for copr-be run")
    parser.add_option('-d','--daemonize', default=False, dest='daemonize',
            action='store_true', help="daemonize or not")
    parser.add_option('-p', '--pidfile', default='copr-be.pid', dest='pidfile',
            help="pid file to use for copr-be if daemonized")
    parser.add_option('-x', '--exit', default=False, dest='exit_on_worker',
            action='store_true', help="exit on worker failure")
            
    opts, args = parser.parse_args(args)
    if not os.path.exists(opts.config_file):
        print "No config file found at: %s" % opts.config_file
        sys.exit(1)
    opts.config_file = os.path.abspath(opts.config_file)
    
    ret_opts = Bunch()
    for o in ('daemonize', 'exit_on_worker', 'pidfile', 'config_file'):
        setattr(ret_opts, o, getattr(opts, o))

    return ret_opts
    
    
    
def main(args):
    opts = parse_args(args)
    
    try:
        cbe = CoprBackend(opts.config_file, ext_opts=opts)
        if opts.daemonize:
            daemonize(opts.pidfile)
        cbe.run()
    except Exception, e:
        print 'Killing/Dying'
        if 'cbe' in locals():
            for w in cbe.workers:
                w.terminate()
        raise
    except KeyboardInterrupt, e:
        pass
    
if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception, e:
        print "ERROR:  %s - %s" % (str(type(e)), str(e))
        # FIXME - maybe check on daemonize and do this as a syslog.syslog() call?
        sys.exit(1)
    except KeyboardInterrupt, e:
        print "\nUser cancelled, may need cleanup\n"
        sys.exit(0)
        
