"""
Copr common code related to redis
"""

from redis import StrictRedis

_connections = {}


def get_redis_connection(opts):
    """
    Creates redis client object using backend config, or returns
    a cached connection if one already exists for the same (host, port, db).

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

    # WARNING: if you use password, note that you shouldn't use this
    # get_redis_connection() helper with two different passwords (password is
    # intentionally not hashed to not keep it in memory on more places).
    cache_key = (
        kwargs.get("host", "localhost"),
        int(kwargs.get("port", 6379)),
        int(kwargs.get("db", 0)),
    )
    if cache_key not in _connections:
        _connections[cache_key] = StrictRedis(
            encoding="utf-8", decode_responses=True, **kwargs)
    return _connections[cache_key]
