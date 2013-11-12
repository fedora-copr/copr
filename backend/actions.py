from callback import FrontendCallback

class Action(object):
    """ Object to send data back to fronted """

    def __init__(self, opts, events, action):
        super(Action, self).__init__()
        self.frontend_callback = FrontendCallback(opts)
        self.data = action
        self.events = events

    def run(self):
        """ Handle action (other then builds) - like rename or delete of project """
        if self.data['action_type'] == 0: # delete
            self.events("Action delete")
        elif self.data['action_type'] == 1: # rename
            self.events("Action rename")
        elif self.data['action_type'] == 2: # legal-flag
            self.events("Action legal-flag: ignoring")
