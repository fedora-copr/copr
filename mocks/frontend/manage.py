#!/usr/bin/python3

from flask.ext.script import Server, Manager
from app import app

manager = Manager(app)
manager.add_command("runserver", Server(use_debugger=True, use_reloader=True))

if __name__ == "__main__":
    manager.run()
