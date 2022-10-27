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
    if hasattr(opts, "redis_db"):
        kwargs["db"] = opts.redis_db
    if hasattr(opts, "redis_host"):
        kwargs["host"] = opts.redis_host
    if hasattr(opts, "redis_port"):
        kwargs["port"] = opts.redis_port

    return StrictRedis(encoding="utf-8", decode_responses=True, **kwargs)
