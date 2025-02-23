"""
OpenId Connect helper functions.
"""
from authlib.integrations.flask_client import OAuth
from coprs import app


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
    if config.get("OIDC_LOGIN") is False:
        # OIDC is an optional feature, don't log anything if it is disabled
        return False

    if not is_config_valid(config):
        app.logger.error("OIDC_LOGIN or OIDC_PROVIDER_NAME is empty")
        return False

    for key in ["OIDC_CLIENT", "OIDC_SECRET", "OIDC_SCOPES"]:
        if not config.get(key):
            app.logger.error("%s is empty", key)
            return False

    if not config.get("OIDC_TOKEN_AUTH_METHOD"):
        app.logger.warning("OIDC_TOKEN_AUTH_METHOD is empty, using default method: client_secret_basic")
        config["OIDC_TOKEN_AUTH_METHOD"] = "client_secret_basic"

    username_claim = config.get("OIDC_USERNAME_CLAIM")
    if username_claim and \
       not username_claim in ("username", "preferred_username"):
        app.logger.error(
            f"Invalid setting {repr(username_claim)} for OIDC_USERNAME_CLAIM, " +
            "expected one of: \"username\", \"preferred_username\""
        )
        return False

    return config.get("OIDC_METADATA") or (
        config.get("OIDC_AUTH_URL")
        and config.get("OIDC_TOKEN_URL")
        and config.get("OIDC_USERINFO_URL")
    )


def oidc_username_from_userinfo(config, userinfo):
    """
    Return a unique user name from UserInfo
    """
    try:
        return userinfo[config.get("OIDC_USERNAME_CLAIM", "username")]
    except KeyError as exc:
        raise RuntimeError(
            "Can't get unique username, see OIDC_USERNAME_CLAIM configuration docs"
        ) from exc


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
