"""
APIv3 /monitor Python client code
"""

from copr.v3 import proxies
from copr.v3.requests import munchify
from copr.v3.helpers import for_all_methods, bind_proxy


@for_all_methods(bind_proxy)
class MonitorProxy(proxies.BaseProxy):
    """
    Proxy to process /api_3/monitor requests.
    """

    def monitor(self, ownername, projectname, project_dirname=None,
                additional_fields=None):
        """
        Return a list of project packages, and corresponding info for the latest
        chroot builds.

        :param str ownername:
        :param str projectname:
        :param str project_dirname:
        :param list additional_fields: List of additional fields to return in
            the dictionary.  Possible values: ``url_build_log``,
            ``url_backend_log``, ``build_url``.  Note that additional fields
            may significantly prolong the server response time.
        :return: Munch a list of dictionaries,
            formatted like::

                {
                  "name": package_name,
                    "chroots": {
                      "fedora-rawhide-x86_64": {
                          "build_id": 843616,
                          "status": "succeeded",
                          ... fields ...,
                    }
                  },
                }
        """
        endpoint = "/monitor"
        params = {
            "ownername": ownername,
            "projectname": projectname,
            "project_dirname": project_dirname,
            "additional_fields[]": additional_fields,
        }
        response = self.request.send(endpoint=endpoint, params=params)
        return munchify(response)
