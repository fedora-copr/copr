import logging
from logging import Formatter
from logging.handlers import SMTPHandler, WatchedFileHandler
import flask

from coprs import app

mail_error_formatter = Formatter("""
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
""")


default_formatter = Formatter(
    "%(asctime)s [%(levelname)s]"
    "[%(pathname)s:%(lineno)d|%(module)s:%(funcName)s][%(user)s] %(message)s"
)


class FlaskUserFilter(logging.Filter):
    """
    Define `%(user)s` key for the formatter string
    """

    def filter(self, record):
        record.user = self._user()
        return True

    def _user(self):
        if not flask.g or not hasattr(flask.g, "user"):
            return "SERVER"

        if flask.g.user:
            return flask.g.user.name

        return self._backend() or "ANON"

    @staticmethod
    def _backend():
        auth = flask.request.authorization
        if auth and auth.password == app.config["BACKEND_PASSWORD"]:
            return "backend: {0}".format(flask.request.remote_addr)
        return None


def setup_log():
    if not app.debug:
        # Send critical message by email
        mail_handler = SMTPHandler(
            "127.0.0.1",
            "copr-fe-error@{0}".format(
                app.config["SERVER_NAME"] or "fedorahosted.org"),
            app.config.get("SEND_LOGS_TO"),
            "Yay, error in copr frontend occurred!")

        mail_handler.setFormatter(mail_error_formatter)
        mail_handler.setLevel(logging.CRITICAL)
        app.logger.addHandler(mail_handler)

    # store all logs to the file log
    log_filename = app.config.get("LOG_FILENAME")
    handler = WatchedFileHandler(log_filename)
    handler.setFormatter(default_formatter)
    log_level_text = app.config.get("LOGGING_LEVEL", 'info')
    log_level = getattr(logging, log_level_text.upper())
    handler.setLevel(log_level)
    app.logger.addFilter(FlaskUserFilter())
    app.logger.setLevel(log_level)
    app.logger.addHandler(handler)

    app.logger.info("logging configuration finished")
