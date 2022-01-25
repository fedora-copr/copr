"""
Init file for `copr` package tests
"""

import os
import six


path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
resource_location = os.path.join(dir_path, "resources")
config_location = os.path.join(resource_location, "copr_cli.conf")

# We need to maintain python2 compatibility for EPEL7
if six.PY3:
    from unittest import mock
else:
    import mock
