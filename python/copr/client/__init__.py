"""
Python client for copr service.
"""

__author__ = 'vgologuz@redhat.com'
__version__ = "1.59.0"

from .client import CoprClient

# for cli backward compatibility
import copr.exceptions as exceptions
