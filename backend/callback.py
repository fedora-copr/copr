import json
import requests

class FrontendCallback(object):
    """ Object to send data back to fronted """

    def __init__(self, opts):
        super(FrontendCallback, self).__init__()
        self.frontend_url = opts.frontend_url
        self.frontend_auth = opts.frontend_auth
        self.msg = None

    def post_to_frontend(self, data):
        """ Send data to frontend """
        headers = {'content-type': 'application/json'}
        url = '%s/update_actions/' % self.frontend_url
        auth = ('user', self.frontend_auth)

        self.msg = None
        try:
            r = requests.post(url, data=json.dumps(data), auth=auth,
                              headers=headers)
            if r.status_code != 200:
                self.msg = 'Failed to submit to frontend: %s: %s' % (r.status_code, r.text)
        except requests.RequestException, e:
            self.msg = 'Post request failed: %s' % e

        if self.msg:
            return False
        else:
            return True

