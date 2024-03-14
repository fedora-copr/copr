"""
Copr common code related to redis
"""

from redis import StrictRedis


def get_redis_connection(opts):
    """
    Creates redis client object using backend config

    :rtype: StrictRedis
    """
    kwargs = {}
    for key in ["db", "host", "port", "password"]:
        config_key = "redis_" + key

        # dict-like objects
        if isinstance(opts, dict):
            if config_key in opts:
                kwargs[key] = opts[config_key]
                continue

        # class-like objects
        if hasattr(opts, config_key):
            kwargs[key] = getattr(opts, config_key)
            continue

    return StrictRedis(encoding="utf-8", decode_responses=True, **kwargs)
