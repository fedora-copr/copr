#!/usr/bin/python3

"""
This is script is supposed to be run daily from lighttpd logrotate, e.g.
   prerotate
       /usr/bin/copr_log_hitcounter.py /var/log/lighttpd/access.log \
           --ignore-subnets 172.25.80.0/20 209.132.184.33/24 || :
   endscript
"""

import re
import os
import logging
import argparse
from datetime import datetime
from copr_common.log import setup_script_logger
from copr_backend.hitcounter import update_frontend


log = logging.getLogger(__name__)
setup_script_logger(log, "/var/log/copr-backend/hitcounter.log")

logline_regex = re.compile(
    r'(?P<ip_address>.*)\s+(?P<hostname>.*)\s+-\s+\[(?P<timestamp>.*)\]\s+'
    r'"GET (?P<url>.*)\s+(?P<protocol>.*)"\s+(?P<code>.*)\s+(?P<bytes_sent>.*)\s+'
    r'"(?P<referer>.*)"\s+"(?P<agent>.*)"', re.IGNORECASE)


def parse_access_file(path):
    """
    Take a raw access file and return its contents as a list of dicts.
    """
    with open(path, 'r') as logfile:
        content = logfile.readlines()
    assert content[0].startswith("=== start:")

    accesses = []
    for line in content[1:]:
        m = logline_regex.match(line)
        if not m:
            continue
        # Rename dict keys to match `copr-aws-s3-hitcounter`
        access = m.groupdict()
        access["cs-uri-stem"] = access.pop("url")
        access["sc-status"] = access.pop("code")
        access["cs(User-Agent)"] = access.pop("agent")
        timestamp = datetime.strptime(access.pop("timestamp"),
                                      "%d/%b/%Y:%H:%M:%S %z")
        access["time"] = timestamp.strftime("%H:%M:%S")
        access["date"] = timestamp.strftime("%Y-%m-%d")
        accesses.append(access)
    return accesses


def get_arg_parser():
    """
    Generate argument parser for this script
    """
    name = os.path.basename(__file__)
    description = 'Read lighttpd access.log and count repo accesses.'
    parser = argparse.ArgumentParser(name, description=description)
    parser.add_argument(
        'logfile',
        action='store',
        help='Path to the input logfile')
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=("Do not perform any destructive changes, only print what "
              "would happen"))
    parser.add_argument(
        "--verbose",
        action="store_true",
        help=("Print verbose information about what is going on"))
    return parser


def main():
    "Main function"
    parser = get_arg_parser()
    args = parser.parse_args()

    if args.verbose:
        log.setLevel(logging.DEBUG)

    # If the access.log gets too big, sending it all at once to frontend will
    # timeout. Let's send it in chunks.
    # The issue is, there is no transaction mechanism, so theoretically some
    # chunks may succeed, some fail and never be counted. But we try to send
    # each request repeatedly and losing some access hits from time to time
    # isn't a mission critical issue and I would just roll with it.
    accesses = parse_access_file(args.logfile)
    size = 1000
    chunks = [accesses[x:x+size] for x in range(0, len(accesses), size)]
    for chunk in chunks:
        update_frontend(chunk, log=log, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
