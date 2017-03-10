#!/usr/bin/python2
# coding: utf-8

from backend.daemons.action_dispatcher import ActionDispatcher
from backend.helpers import get_backend_opts

def main():
    action_dispatcher = ActionDispatcher(get_backend_opts())
    action_dispatcher.run()

if __name__ == "__main__":
    main()
