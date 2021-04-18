"""
Init file for `copr` package tests
"""

import os

path = os.path.abspath(__file__)
dir_path = os.path.dirname(path)
resource_location = os.path.join(dir_path, "resources")
config_location = os.path.join(resource_location, "copr_cli.conf")
