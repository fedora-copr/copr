import base64
import flask

from coprs import app

webhooks_ns = flask.Blueprint("webhooks_ns", __name__, url_prefix="/webhooks")

@webhooks_ns.after_request
def after_request(response):
    """
    Dump the webhook payloads for later debugging and auditing.
    """
    request = flask.request
    status = response.status_code
    prefix = "Webhook ({}) ".format(status)

    # 100k should be enough for most of the webhooks.  We don't want to waste
    # the /var/log partition too quickly.
    if request.content_length is not None \
            and request.content_length >= 100*1024:
        app.logger.info(prefix+"large content: %d bytes",
                        request.content_length)
        return response

    app.logger.info(prefix+"data: %s", base64.b64encode(request.get_data()))
    return response
