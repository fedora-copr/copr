#!/usr/bin/python3

import logging
import os

import sys
import pwd

logging.basicConfig(
    filename="/var/log/copr-backend/copr_createrepo.log",
    format='[%(asctime)s][%(levelname)6s]: %(message)s',
    level=logging.INFO)
log = logging.getLogger(__name__)


from copr_backend.createrepo import createrepo
from copr_backend.helpers import SortedOptParser, BackendConfigReader


def main(args):

    parser = SortedOptParser(
        "copr_create_repo")

    parser.add_option("-u", "--user", dest="user",
                      help="copr project owner username")

    parser.add_option("-p", "--project", dest="project",
                      help="copr project name")

    parser.add_option("-f", "--front_url", dest="front_url",
                      help="copr frontend url")

    cli_opts, args = parser.parse_args(args)

    if not cli_opts.user:
        print("No user was specified, exiting", file=sys.stderr)
        sys.exit(1)

    if not cli_opts.project:
        print("No project was specified, exiting", file=sys.stderr)
        sys.exit(1)

    opts = BackendConfigReader().read()

    front_url = cli_opts.front_url or opts.frontend_base_url
    project_path = os.path.join(opts.destdir, cli_opts.user, cli_opts.project)

    log.info("start processing {}/{}".format(cli_opts.user, cli_opts.project))
    for subdir in os.listdir(project_path):
        if os.path.isdir(subdir):
            path = os.path.join(project_path, subdir)
            log.info("entering dir: {}".format(subdir))
            createrepo(path=path, front_url=front_url,
                       username=cli_opts.user, projectname=cli_opts.project)
            log.info("done dir: {}".format(subdir))
    log.info("finished processing {}/{}".format(cli_opts.user, cli_opts.project))

if __name__ == "__main__":
    """
        Provides cli interface for conditional execution of createrepo_c
              depending on user setting `auto_createrepo`
    """
    if pwd.getpwuid(os.getuid())[0] != "copr":
        print("This script should be executed under the `copr` user")
        sys.exit(1)
    else:
        main(sys.argv[1:])


#with open("coprs_to_cr.txt") as inp:
#    with open("cr_cmd_list.txt", "w") as outp:
#        for line in inp:
#            copr, user = line.strip().split("/")
#            outp.write("{} -u {} -p {}\n".format("/usr/bin/copr_createrepo.py", copr, user))
