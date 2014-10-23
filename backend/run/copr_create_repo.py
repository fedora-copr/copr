from __future__ import print_function

import sys

from backend.createrepo import createrepo
from backend.helpers import SortedOptParser


def main(args):

    parser = SortedOptParser(
        "mockremote -u user_name -p copr_project repo_dir")

    parser.add_option("-u", "--user", dest="user",
                      help="copr project owner username")

    parser.add_option("-p", "--project", dest="project",
                      help="copr project name")

    parser.add_option("-f", "--front_url", dest="front_url",
                      help="copr frontend url")

    opts, args = parser.parse_args(args)

    if not opts.user:
        print("No user was specified, exiting", file=sys.stderr)
        sys.exit(1)

    if not opts.project:
        print("No project was specified, exiting", file=sys.stderr)
        sys.exit(1)

    if not opts.front_url:
        print("No api url was specified, exiting", file=sys.stderr)
        sys.exit(1)

    if not args:
        print("No directory with repo was specified, exiting", file=sys.stderr)
        sys.exit(1)

    result = createrepo(path=args[0], front_url=opts.front_url,
                        username=opts.user, projectname=opts.project)
    if not result:
        print("Createrepo was skipped")
    else:
        retcode, stdout, stderr = result
        print("STDOUT: {}".format(stdout))
        print("STDERR: {}".format(stderr))


if __name__ == "__main__":
    """
        Provides cli interface for conditional execution of createrepo_c
              depending on user setting `auto_createrepo`
    """
    main(sys.argv[1:])
