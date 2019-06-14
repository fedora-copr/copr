:orphan:

.. _webhook_hacking:

COPR auto-rebuilds with custom Git repositories
===============================================

Even if your Git repository is not hosted on Gitlab, Github, Bitbucket or Pagure, you can still have continuous integration with COPR. That is, you can launch auto-rebuilds on push events. It just requires a bit more work and access to the server where the repository is hosted.

In your bare Git repository on the server, place the following
code into yourrepo.git/hooks/post-receive (the file should be executable)::

    #!/usr/bin/python

    import requests
    import sys
    import json

    while True:
        line = sys.stdin.readline()
        if not line:
            break

        old_value, new_value, ref_name = line.split()

        payload = {
            "object_kind": "push",
            "before": old_value,
            "after": new_value,
            "ref": ref_name,
            "project": {
                # this needs to be the same as "SCM URL" for SCM-2 method
                "git_http_url": "https://yourserver/yourrepo.git",
            },
        }

        webhook_url = "https://copr.fedorainfracloud.org/webhooks/gitlab/5642/393984f7-4c72-4c41-ba70-7f0abd54b3de/"
        r = requests.post(webhook_url, json=payload)


This code is invoked when new ref is pushed (you can read more `here <https://git-scm.com/docs/githooks#post-receive>`_).
You need to replace `webhook_url` value with the actual webhook url for your COPR project. You can find these under
Settings/Webhooks in your project and you should use the Gitlab webhook url because we are using Gitlab-formatted payload
in this example.

This approach is currently only possible with SCM-2 (previously MockSCM) source-type because SCM-1 (previously Tito) checks
also for modified files in the received payload and you would need to supply this information in 'commits' field additionally
(see https://docs.gitlab.com/ee/user/project/integrations/webhooks.html#push-events and the example message in that section
to see how the 'commits' field should look like).
