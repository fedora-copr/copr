#!/usr/bin/python -tt


import os
import sys
import multiprocessing
import time
import Queue
import json
import mockremote
from bunch import Bunch
import errors
import ansible
import ansible.playbook
import ansible.errors
from ansible import callbacks





class SilentPlaybookCallbacks(callbacks.object):
    ''' playbook callbacks - quietly! '''

    def __init__(self, verbose=False):

        self.verbose = verbose

    def on_start(self):
        callbacks.call_callback_module('playbook_on_start')

    def on_notify(self, host, handler):
        callbacks.call_callback_module('playbook_on_notify', host, handler)

    def on_no_hosts_matched(self):
        callbacks.call_callback_module('playbook_on_no_hosts_matched')

    def on_no_hosts_remaining(self):
        callbacks.call_callback_module('playbook_on_no_hosts_remaining')

    def on_task_start(self, name, is_conditional):
        callbacks.call_callback_module('playbook_on_task_start', name, is_conditional)

    def on_vars_prompt(self, varname, private=True, prompt=None, encrypt=None, confirm=False, salt_size=None, salt=None):
        result = None
        print "***** VARS_PROMPT WILL NOT BE RUN IN THIS KIND OF PLAYBOOK *****"
        callbacks.call_callback_module('playbook_on_vars_prompt', varname, private=private, prompt=prompt, encrypt=encrypt, confirm=confirm, salt_size=salt_size, salt=None)
        return result

    def on_setup(self):
        callbacks.call_callback_module('playbook_on_setup')

    def on_import_for_host(self, host, imported_file):
        callbacks.call_callback_module('playbook_on_import_for_host', host, imported_file)

    def on_not_import_for_host(self, host, missing_file):
        callbacks.call_callback_module('playbook_on_not_import_for_host', host, missing_file)

    def on_play_start(self, pattern):
        callbacks.call_callback_module('playbook_on_play_start', pattern)

    def on_stats(self, stats):
        callbacks.call_callback_module('playbook_on_stats', stats)


class WorkerCallback(object):
    def __init__(self, logfile=None):
        self.logfile = logfile
    
    def log(self, msg):
        if not self.logfile:
            return
            
        now = time.time()
        try:
            open(self.logfile, 'a').write(str(now) + ':' + msg + '\n')
        except (IOError, OSError), e:
            print >>sys.stderr, 'Could not write to logfile %s - %s' % (self.logfile, str(e))
            
        
class Worker(multiprocessing.Process):
    def __init__(self, opts, jobs, ip=None, create=True, callback=None):
 
        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")
        
            
        # job management stuff
        self.jobs = jobs
        self.ip = ip
        self.opts = opts
        self.kill_received = False
        self.callback = callback
        if not self.callback:
            lf = self.opts.worker_logdir + '/worker-%s.log'  % self.pid
            self.callback = WorkerCallback(logfile = lf)
        
        self.callback.log('creating worker: %s' % ip)

    def spawn_instance(self):
        
        stats = callbacks.AggregateStats()
        playbook_cb = SilentPlaybookCallbacks(verbose=False)
        runner_cb = callbacks.DefaultRunnerCallbacks()
        # fixme - extra_vars to include ip as a var if we need to specify ips
        # also to include info for instance type to handle the memory requirements of builds
        play = ansible.playbook.PlayBook(stats=stats, playbook=self.opts.playbook, 
                             callbacks=playbook_cb, runner_callbacks=runner_cb, 
                             remote_user='root')

        play.run()
        if self.ip:
            return self.ip
            
        for i in play.SETUP_CACHE:
            if i =='localhost':
                continue
            return i
        return None
    
    def parse_job(self, jobfile):
        # read the json of the job in
        # break out what we need return a bunch of the info we need
        d = json.load(open(jobfile))
        build = d['builds'][0]
        jobdata = Bunch()
        jobdata.pkgs = build['pkgs'].split(' ')
        jobdata.repos = build['repos'].split(' ')
        jobdata.chroots = build['chroots'].split(' ')
        jobdata.memory_reqs = build['memory_reqs']
        jobdata.timeout = build['timeout']
        jobdata.destdir = self.opts.destdir + '/' + build['copr']['owner']['name'] + '/' + build['copr']['name'] + '/'
        jobdata.build_id = build['id']
        jobdata.copr_id = build['copr']['id']
        jobdata.user_id = build['user_id']
        return jobdata

    def return_results(self, job):
        self.log('%s status %s. Took %s seconds' % (job.id, job.status, job.ended_on - job.startedon))
        os.unlink(job.jobfile)
        #FIXME - this should either return job status/results 
        # into a queue or it should submit results directly to the frontend
        
    def run(self):
        # worker should startup and check if it can function
        # for each job it takes from the jobs queue
        # run opts.setup_playbook to create the instance
        # do the build (mockremote)
        # terminate the instance

        while not self.kill_received:
            try:
                jobfile = self.jobs.get()
            except Queue.Empty:
                break
            
            # parse the job json into our info
            job = self.parse_job(jobfile)
            
            job.jobfile = jobfile
            
            # spin up our build instance
            try:
                ip = self.spawn_instance()
                if not ip:
                    raise errors.CoprWorkerError, "No IP found from creating instance"

            except ansible.errors.AnsibleError, e:
                self.callback.log('failure to setup instance: %s' % e)
                raise

            status = 1
            job.started_on = time.time()
            for chroot in job.chroots:
                self.callback.log('mockremote on %s - %s' % (ip, jobfile))
                try:
                    mr = mockremote.MockRemote(builder=ip, timeout=job.timeout, 
                         destdir=job.destdir, chroot=chroot, cont=True, recurse=True,
                         repos=job.repos, callback=None)
                    mr.build_pkgs(job.pkgs)
                except mockremote.MockRemoteError, e:
                    # record and break
                    self.callback.log('%s - %s' % (ip, e))
                    status = 0 # failure
            
            job.ended_on = time.time()
            job.status = status
            self.return_results(job)
            
            
            

