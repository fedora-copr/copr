#!/usr/bin/python2
# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

from backend.helpers import get_backend_opts
from backend.daemons.log import RedisLogHandler


def main():
    opts = get_backend_opts()
    handler = RedisLogHandler(opts)
    handler.run()


if __name__ == "__main__":
    main()
