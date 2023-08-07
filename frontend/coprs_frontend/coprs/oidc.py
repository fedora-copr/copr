"""
OpenId Connect helper functions.
"""
import logging
from authlib.integrations.flask_client import OAuth

logger = logging.getLogger(__name__)


def is_config_valid(config):
    """
    If OpenID Connect is enabled
    """
    return "OIDC_LOGIN" in config and config["OIDC_LOGIN"] is True and \
            "OIDC_PROVIDER_NAME" in config and config["OIDC_PROVIDER_NAME"]


def oidc_enabled(config):
    """
    Check whether the config is valid
    """
    if not is_config_valid(config):
        logger.error("OIDC_LOGIN or OIDC_PROVIDER_NAME is empty")
        return False

    if not config.get("OIDC_CLIENT"):
        logger.error("OIDC_CLIENT is empty")
        return False

    if not config.get("OIDC_SECRET"):
        logger.error("OIDC_SECRET is empty")
        return False

    if not config.get("OIDC_SCOPES"):
        logger.error("OIDC_SCOPES is empty")
        return False

    if not config.get("OIDC_TOKEN_AUTH_METHOD"):
        logger.warning("OIDC_SCOPES is empty, using default method: client_secret_basic")
        config["OIDC_TOKEN_AUTH_METHOD"] = "client_secret_basic"

    return config.get("OIDC_METADATA") or (
        config.get("OIDC_AUTH_URL")
        and config.get("OIDC_TOKEN_URL")
        and config.get("OIDC_USERINFO_URL")
    )


def init_oidc_app(app):
    """
    Init a openID connect client using configs
    When configs check failed, a invalid client object is returned
    """
    oidc = OAuth(app)
    if oidc_enabled(app.config):
        client_id = app.config.get("OIDC_CLIENT")
        secret = app.config.get("OIDC_SECRET")
        client_kwargs = {
            "scope": app.config.get("OIDC_SCOPES"),
            "token_endpoint_auth_method": app.config.get("OIDC_TOKEN_AUTH_METHOD"),
        }
        if app.config.get("OIDC_METADATA"):
            oidc.register(
                name="copr",
                server_metadata_url=app.config.get("OIDC_METADATA"),
                client_id=client_id,
                client_secret=secret,
                client_kwargs=client_kwargs,
            )
        else:
            oidc.register(
                name="copr",
                client_id=client_id,
                client_secret=secret,
                access_token_url=app.config.get("OIDC_TOKEN_URL"),
                authorize_url=app.config.get("OIDC_AUTH_URL"),
                userinfo_endpoint=app.config.get("OIDC_USERINFO_URL"),
                client_kwargs=client_kwargs,
            )
    return oidc
