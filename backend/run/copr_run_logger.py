#!/usr/bin/python3
# coding: utf-8

import sentry_sdk
from copr_backend.helpers import get_backend_opts
from copr_backend.daemons.log import RedisLogHandler


def main():
    opts = get_backend_opts()
    if opts["sentry_dsn"]:
        sentry_sdk.init(dsn=opts["sentry_dsn"])

    handler = RedisLogHandler(opts)
    handler.run()


if __name__ == "__main__":
    main()
