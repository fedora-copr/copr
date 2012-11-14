#!/usr/bin/python -tt


import sys
import os
import glob
import time
import json
import multiprocessing
from backend.dispatcher import Worker
from bunch import Bunch
from ConfigParser import ConfigParser

def _get_conf(cp, section, option, default):
    """to make returning items from config parser less irritating"""
    if cp.has_section(section) and cp.has_option(section,option):
        return cp.get(section, option)
    return default
        
class CoprBackendError(Exception):

    def __init__(self, msg):
        self.msg = msg
    
    def __str__(self):
        return self.msg

class CoprBackend(object):
    def __init__(self, config_file=None):
        # read in config file
        # put all the config items into a single self.opts bunch
        
        if not config_file:
            raise CoprBackendError, "Must specify config_file"
        
        self.config_file = config_file
        self.opts = self.read_config()

        self.jobs = multiprocessing.Queue()
        self.workers = []
        self.added_jobs = []

        # setup a log file to write to
        self.logfile = self.opts.logfile

    def read_conf(self):
        "read in config file - return Bunch of config data"
        opts = Bunch()
        cp = ConfigParser.ConfigParser()
        try:
            cp.read(self.config_file)
            opts.results_baseurl = _get_conf(cp,'backend', 'results_baseurl', 'http://copr')
            opts.frontend_url = _get_config(cp, 'backend', 'frontend_url', 'http://coprs/rest/api')
            opts.frontend_auth = _get_conf(cp,'backend', 'frontend_auth', 'PASSWORDHERE')
            opts.playbook = _get_conf(cp,'backend','playbook', '/etc/copr/builder_playbook.yml')
            opts.jobsdir = _get_conf(cp, 'backend', 'jobsdir', None)
            opts.destdir = _get_conf(cp, 'backend', 'destdir', None)
            opts.sleeptime = int(_get_conf(cp, 'backend', 'sleeptime', 10))
            opts.num_workers = int(_get_conf(cp, 'backend', 'num_workers', 8))
            opts.timeout = int(_get_conf(cp, 'builder', 'timeout', 1800))
            opts.logfile = _get_conf(cp, 'backend', 'logfile', '/var/log/copr-be.log')
            # thoughts for later
            # ssh key for connecting to builders?
            # cloud key stuff?
            # 
        except ConfigParser.Error, e:
            raise CoprBackendError, 'Error parsing config file: %s: %s' % (self.config_file, e)
        
        
        if not opts.jobsdir or not opts.destdir:
            raise CoprBackendError, "Incomplete Config - must specify jobsdir and destdir in configuration"
            
        return opts
        
        
    def log(self, msg):
        if self.logfile:
            now = time.time()
            try:
                open(self.logfn, 'a').write(str(now) + ':' + msg + '\n')
            except (IOError, OSError), e:
                print >>sys.stderr, 'Could not write to logfile %s - %s' % (self.lf, str(e))
        if not self.quiet:
            print msg


    def run(self):
        # start processing builds, etc
        # setup and run our workers
        for i in range(opts.num_workers):
            w = backend.dispatcher.Worker(opts, jobs)
            workers.append(w)
            w.start()

        abort = False
        while not abort:
            print 'adding jobs'
            for f in sorted(glob.glob(jobsdir + '/*.json')):
                n = os.path.basename(f).replace('.json', '')
                if not is_completed(n) and n not in added:
                    #jobdata = open(f).read()
                    jobs.put(n)
                    added.append(n)
                    print 'adding %s' % n



            print "# jobs in queue: %s" % jobs.qsize()


        # FIXME:
        # look up number of workers in config
        # see if it changed and update accordingly?
        # poison pill? if opts.num_workers < len(workers)?
        time.sleep(opts.sleeptime)
        

def is_completed(jobid):

    if glob.glob(destdir + '/' + jobid + '*'):
        return True
    return False
    
def main(args):
            
    


    
if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except Exception, e:
        print "ERROR:  %s - %s" % (str(type(e)), str(e))
        sys.exit(1)
    except KeyboardInterrupt, e:
        print "\nUser cancelled, need cleanup\n"
        sys.exit(0)
        
