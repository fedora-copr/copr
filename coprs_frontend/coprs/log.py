import logging
import logging.handlers

from coprs import app

send_logs_to = app.config.get("SEND_LOGS_TO")
level = app.config.get("LOGGING_LEVEL")

formatter = logging.Formatter("""
Message type:       %(levelname)s
Location:           %(pathname)s:%(lineno)d
Module:             %(module)s
Function:           %(funcName)s
Time:               %(asctime)s

Message:

%(message)s
""")

if not app.debug:
    mail_handler = logging.handlers.SMTPHandler(
        "127.0.0.1",
        "copr-fe-error@{0}".format(
            app.config["SERVER_NAME"] or "fedorahosted.org"),
        send_logs_to,
        "Yay, error in copr frontend occured!")

    mail_handler.setFormatter(formatter)
    mail_handler.setLevel(level)
    app.logger.addHandler(mail_handler)
