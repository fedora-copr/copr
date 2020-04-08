#!/usr/bin/python3
# coding: utf-8

from copr_backend.daemons.build_dispatcher import BuildDispatcher
from copr_backend.helpers import get_backend_opts


def main():
    build_dispatcher = BuildDispatcher(get_backend_opts())
    build_dispatcher.run()


if __name__ == "__main__":
    main()
