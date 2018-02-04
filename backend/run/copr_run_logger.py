#!/usr/bin/python3
# coding: utf-8

from backend.helpers import get_backend_opts
from backend.daemons.log import RedisLogHandler


def main():
    opts = get_backend_opts()
    handler = RedisLogHandler(opts)
    handler.run()


if __name__ == "__main__":
    main()
