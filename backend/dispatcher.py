#!/usr/bin/python -tt


import sys
import os
import glob
import subprocess
import multiprocessing
import time
import Queue
import json
import mockremote
from bunch import Bunch
import ansible
import ansible.playbook
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

def spawn_instance(opts, ip):
    
    # FIXME - setup silent callbacks
    #       - check errors in setup
    #       - playbook variablized
    stats = callbacks.AggregateStats()
    playbook_cb = SilentPlaybookCallbacks(verbose=False)
    runner_cb = callbacks.DefaultRunnerCallbacks()
    play = ansible.playbook.PlayBook(stats=stats, playbook='/srv/copr-work/provision/builderpb.yml', 
                             callbacks=playbook_cb, runner_callbacks=runner_cb, remote_user='root')

    play.run()
    if ip:
        return ip
        
    for i in play.SETUP_CACHE:
        if i =='localhost':
            continue
        return i

class Worker(multiprocessing.Process):
    def __init__(self, opts, jobs, ip=None, create=True, callback=None):
 
        # base class initialization
        multiprocessing.Process.__init__(self, name="worker-builder")
 
        # job management stuff
        self.jobs = jobs
        self.ip = ip
        self.opts = opts
        self.kill_received = False
        print 'creating worker: %s' % ip

    
    def parse_job(job):
        # read the json of the job in
        # break out what we need return a structured 
    def run(self):
        # worker should startup and check if it can function
        # for each job it takes from the jobs queue
        # run opts.setup_playbook to create the instance
        # do the build (mockremote)
        # terminate the instance

        while not self.kill_received:
            try:
                job = self.jobs.get()
            except Queue.Empty:
                break
            
            self.cur_job = job
            f = open(self.opts.get('destdir', '/') + '/' +  job, 'w')
            f.write('')
            f.close()
            
            # parse the job json into our info
            # pkgs
            # repos
            # chroot(s)
            # memory needed
            # timeout
            # make up a destdir
            
            #print 'start up instance %s using %s' % (self.ip, self.opts.get('playbook', None))
            ip = spawn_instance(self.opts, ip=ip)
            
            destdir = construct_something_here
            
            try:
                mr = mockremote.MockRemote(builder=ip, timeout=timeout, 
                     destdir=destdir, chroot=chroot, cont=True, recurse=True,
                     repos=repos, callback=None)
                mr.build_pkgs(pkgs)
            except mockremote.MockRemoteError, e:
                # record and break
                print '%s - %s' % (ip, e)
                break
            
            # run mockremote to that ip with the args from above
            print 'mockremote on %s - %s' % (ip, job)
            time.sleep(30)
            #print 'terminate-instance %s' % (self. ip)
            

