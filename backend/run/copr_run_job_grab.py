#!/usr/bin/python2
# coding: utf-8

from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

from backend.helpers import get_backend_opts
from backend.daemons.job_grab import CoprJobGrab
from backend.frontend import FrontendClient


def main():
    opts = get_backend_opts()
    fc = FrontendClient(opts)
    grabber = CoprJobGrab(opts, frontend_client=fc)
    grabber.run()


if __name__ == "__main__":
    main()
