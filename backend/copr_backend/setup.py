"""
Singleton-like objects to simplify ubiquitous Copr Backend configuration.
"""

from copr_backend.app import App

# the application
app = App()

# configuration, usually in /etc/copr/copr-be.conf
config = app.opts

# the default logger
log = app.log
