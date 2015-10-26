"""
Python client for copr service.
"""

__author__ = 'vgologuz@redhat.com'

from .client import CoprClient

# for cli backward compatibility
import copr.exceptions as exceptions
