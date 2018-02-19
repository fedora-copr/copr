import logging
import os
import sys

# so that errors are not sent to stdout
logging.basicConfig(stream=sys.stderr)

os.environ["COPRS_ENVIRON_PRODUCTION"] = "1"
sys.path.insert(0, os.path.dirname(__file__))

from copr_keygen import app as application
