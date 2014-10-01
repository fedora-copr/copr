#!/usr/bin/python3

import sys
sys.path.append("../src/")

import os
import glob
os.environ["COPR_KEYGEN_CONFIG"] = glob.glob("./run/dev_run.conf")

for d in [
    "/tmp/copr-keygen/var/lib/copr-keygen/phrases/",
    "/tmp/copr-keygen/var/lib/copr-keygen/gnupg",
    "/tmp/copr-keygen/var/log/copr-keygen"
]:
    if not os.path.exists(d):
        os.makedirs(d)

from copr_keygen import app

import logging

logging.basicConfig(
    level=logging.DEBUG,
    format= '[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)

if __name__ == '__main__':
    app.run()
