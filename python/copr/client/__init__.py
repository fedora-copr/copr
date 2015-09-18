"""
Python client for copr service.
"""

__author__ = 'vgologuz@redhat.com'
__version__ = "0.0.1"
__description__ = "Python client for copr service."

from .client import CoprClient

# for cli backward compatibility
import copr.exceptions as exceptions
