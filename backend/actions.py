from bunch import Bunch
from callback import FrontendCallback
import os.path
import shutil
import time

class Action(object):
    """ Object to send data back to fronted """

    def __init__(self, opts, events, action):
        super(Action, self).__init__()
        self.frontend_callback = FrontendCallback(opts)
        self.destdir = opts.destdir
        self.data = action
        self.events = events

    def event(self, what):
        self.events.put({'when':time.time(), 'who':'action', 'what':what})

    def run(self):
        """ Handle action (other then builds) - like rename or delete of project """
        result = Bunch()
        result.id = self.data['id']
        if self.data['action_type'] == 0: # delete
            self.event("Action delete")
            project = self.data['old_value']
            path = os.path.normpath(self.destdir + '/' + project)
            if os.path.exists(path):
                self.events('Removing %s' % path)
                shutil.rmtree(path)
            result.job_ended_on = time.time()
            result.result = 1 # success
        elif self.data['action_type'] == 1: # rename
            self.event("Action rename")
            old_path = os.path.normpath(self.destdir + '/', self.data['old_value'])
            new_path = os.path.normpath(self.destdir + '/', self.data['new_value'])
            if os.path.exists(old_path):
                if not os.path.exists(new_path):
                    shutil.move(old_path, new_path)
                    result.result = 1 # success
                else:
                    result.message = 'Destination directory already exist.'
                    result.result = 2 # failure
            else: # nothing to do, that is success too
                result.result = 1 # success
            result.job_ended_on = time.time()
        elif self.data['action_type'] == 2: # legal-flag
            self.event("Action legal-flag: ignoring")
        if 'result' in result:
            self.frontend_callback.post_to_frontend( {'actions': [result]} )
