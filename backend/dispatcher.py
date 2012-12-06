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
import requests




class SilentPlaybookCallbacks(callbacks.PlaybookCallbacks):
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
            
        now = time.strftime('%F %T')
        try:
            open(self.logfile, 'a').write(str(now) + ': ' + msg + '\n')
        except (IOError, OSError), e:
            print >>sys.stderr, 'Could not write to logfile %s - %s' % (self.logfile, str(e))
            
        
class Worker(multiprocessing.Process):
    def __init__(self, opts, jobs, worker_num, ip=None, create=True, callback=None):
 
        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")
        
            
        # job management stuff
        self.jobs = jobs
        self.worker_num = worker_num
        self.ip = ip
        self.opts = opts
        self.kill_received = False
        self.callback = callback
        self.create = create
        if not self.callback:
            self.logfile = self.opts.worker_logdir + '/worker-%s.log' % self.worker_num
            self.callback = WorkerCallback(logfile = self.logfile)
        
        if ip:
            self.callback.log('creating worker: %s' % ip)
        else:
            self.callback.log('creating worker: dynamic ip')

    def spawn_instance(self):
        """call the spawn playbook to startup/provision a building instance"""
        self.callback.log('spawning instance begin')
        
        stats = callbacks.AggregateStats()
        playbook_cb = SilentPlaybookCallbacks(verbose=False)
        runner_cb = callbacks.DefaultRunnerCallbacks()
        # fixme - extra_vars to include ip as a var if we need to specify ips
        # also to include info for instance type to handle the memory requirements of builds
        play = ansible.playbook.PlayBook(stats=stats, playbook=self.opts.spawn_playbook, 
                             callbacks=playbook_cb, runner_callbacks=runner_cb, 
                             remote_user='root')

        play.run()
        self.callback.log('spawning instance end')
        if self.ip:
            return self.ip
            
        for i in play.SETUP_CACHE:
            if i =='localhost':
                continue
            return i
        
        # if we get here we're in trouble
        self.callback.log('No IP back from spawn_instance - dumping cache output')
        self.callback.log(str(play.SETUP_CACHE))
        self.callback.log(str(play.stats.summarize('localhost')))
        self.callback.log('Test spawn_instance playbook manually')
        
        return None

    def terminate_instance(self,ip):
        """call the terminate playbook to destroy the building instance"""
        self.callback.log('terminate instance begin')
        
        stats = callbacks.AggregateStats()
        playbook_cb = SilentPlaybookCallbacks(verbose=False)
        runner_cb = callbacks.DefaultRunnerCallbacks()
        play = ansible.playbook.PlayBook(host_list=[ip], stats=stats, playbook=self.opts.terminate_playbook, 
                             callbacks=playbook_cb, runner_callbacks=runner_cb, 
                             remote_user='root')

        play.run()
        self.callback.log('terminate instance end')
    
    def parse_job(self, jobfile):
        # read the json of the job in
        # break out what we need return a bunch of the info we need
        build = json.load(open(jobfile))
        jobdata = Bunch()
        jobdata.pkgs = build['pkgs'].split(' ')
        jobdata.repos = [r for r in build['repos'].split(' ') if r.strip() ]
        jobdata.chroots = build['chroots'].split(' ')
        jobdata.memory_reqs = build['memory_reqs']
        jobdata.timeout = build['timeout']
        jobdata.destdir = self.opts.destdir + '/' + build['copr']['owner']['name'] + '/' + build['copr']['name'] + '/'
        jobdata.build_id = build['id']
        jobdata.results = self.opts.results_baseurl + '/' + build['copr']['owner']['name'] + '/' + build['copr']['name'] + '/'
        jobdata.copr_id = build['copr']['id']
        jobdata.user_id = build['user_id']
        return jobdata

    # maybe we move this to the callback?
    def post_to_frontend(self, data):
        """send data to frontend"""
        
        headers = {'content-type': 'application/json'}
        url='%s/update_builds/' % self.opts.frontend_url
        auth=('user', self.opts.frontend_auth)
        
        msg = None
        try:
            r = requests.post(url, data=json.dumps(data), auth=auth, 
                              headers=headers)
            if r.status_code != 200:
                msg = 'Failed to submit to frontend: %s: %s' % (r.status_code, r.text)
        except requests.RequestException, e:
            msg = 'Post request failed: %s' % e
            
        if msg:
            self.callback.log(msg)
            return False

        return True
    
    # maybe we move this to the callback?
    def mark_started(self, job):
        
        build = {'id':job.build_id,
                 'started_on': job.started_on,
                 'results': job.results,
                 }
        data = {'builds':[build]}
        
        if not self.post_to_frontend(data):
            raise errors.CoprWorkerError, "Could not communicate to front end to submit status info"
    
    # maybe we move this to the callback?    
    def return_results(self, job):
        self.callback.log('%s status %s. Took %s seconds' % (job.build_id, job.status, job.ended_on - job.started_on))

        build = {'id':job.build_id,
                 'ended_on': job.ended_on,
                 'status': job.status,
                 }
        data = {'builds':[build]}
        
        if not self.post_to_frontend(data):
            raise errors.CoprWorkerError, "Could not communicate to front end to submit results"

        os.unlink(job.jobfile)

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
            
            # FIXME
            # this is our best place to sanity check the job before starting
            # up any longer process
            
            job.jobfile = jobfile
            
            # spin up our build instance
            if self.create:
                try:
                    ip = self.spawn_instance()
                    if not ip:
                        raise errors.CoprWorkerError, "No IP found from creating instance"

                except ansible.errors.AnsibleError, e:
                    self.callback.log('failure to setup instance: %s' % e)
                    raise

            status = 1
            job.started_on = time.time()
            self.mark_started(job)
            
            for chroot in job.chroots:
                
                chroot_destdir = job.destdir + '/' + chroot
                # setup our target dir locally
                if not os.path.exists(chroot_destdir):
                    try:
                        os.makedirs(chroot_destdir)
                    except (OSError, IOError), e:
                        msg = "Could not make results dir for job: %s - %s" % (chroot_destdir, str(e))
                        self.callback.log(msg)
                        status = 0
                        continue

                # FIXME
                # need a plugin hook or some mechanism to check random
                # info about the pkgs
                # this should use ansible to download the pkg on the remote system
                # and run a series of checks on the package before we
                # start the build - most importantly license checks.
                
                        
                self.callback.log('Starting build: builder=%r timeout=%r destdir=%r chroot=%r repos=%r' % (ip, job.timeout, job.destdir, chroot, str(job.repos)))
                try:
                    chrootlogfile = chroot_destdir + '/mockremote.log'
                    mr = mockremote.MockRemote(builder=ip, timeout=job.timeout, 
                         destdir=job.destdir, chroot=chroot, cont=True, recurse=True,
                         repos=job.repos, 
                         callback=mockremote.CliLogCallBack(quiet=True,logfn=chrootlogfile))
                    mr.build_pkgs(job.pkgs)
                except mockremote.MockRemoteError, e:
                    # record and break
                    self.callback.log('%s - %s' % (ip, e))
                    status = 0 # failure
                self.callback.log('Finished build: builder=%r timeout=%r destdir=%r chroot=%r repos=%r' % (ip, job.timeout, job.destdir, chroot, str(job.repos)))
                
            job.ended_on = time.time()
            job.status = status
            self.return_results(job)
            self.callback.log('worker finished build: %s' % ip)
            # clean up the instance
            if self.create:
                self.terminate_instance(ip)

