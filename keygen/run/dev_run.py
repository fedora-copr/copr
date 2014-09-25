#!/usr/bin/python3

import sys
sys.path.append("../src/")
from copr_keygen import app

import logging

logging.basicConfig(
    level=logging.INFO,
    format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

if __name__ == '__main__':
    app.run()
