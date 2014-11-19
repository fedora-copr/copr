from __future__ import print_function
from __future__ import unicode_literals
from __future__ import division
from __future__ import absolute_import

import sys
import os

from backend.exceptions import MockRemoteError
from backend.mockremote import MockRemote, DEF_CHROOT, DEF_BUILD_USER, DEF_REPOS, DEF_TIMEOUT, DEF_DESTDIR
from backend.helpers import SortedOptParser
from backend.mockremote.callback import CliLogCallBack


def read_list_from_file(fn):
    lst = []
    with open(fn) as f:
        for line in f.readlines():
            line = line.replace("\n", "")
            line = line.strip()
            if line.startswith("#"):
                continue
            lst.append(line)

    return lst


def parse_args(args):

    parser = SortedOptParser(
        "mockremote -b hostname -u user -r chroot pkg pkg pkg")
    parser.add_option("-r", "--root", default=DEF_CHROOT, dest="chroot",
                      help="chroot config name/base to use in the mock build")
    parser.add_option("-c", "--continue", default=False, action="store_true",
                      dest="cont",
                      help="if a pkg fails to build, continue to the next one")
    parser.add_option("-a", "--addrepo", default=DEF_REPOS, action="append",
                      dest="repos",
                      help="add these repo baseurls to the chroot's yum config")
    parser.add_option("--recurse", default=False, action="store_true",
                      help="if more than one pkg and it fails to build,"
                      " try to build the rest and come back to it")
    parser.add_option("--log", default=None, dest="logfile",
                      help="log to the file named by this option,"
                      " defaults to not logging")
    parser.add_option("-b", "--builder", dest="builder", default=None,
                      help="builder to use")
    parser.add_option("-u", dest="user", default=DEF_BUILD_USER,
                      help="user to run as/connect as on builder systems")
    parser.add_option("-t", "--timeout", dest="timeout", type="int",
                      default=DEF_TIMEOUT,
                      help="maximum time in seconds a build can take to run")
    parser.add_option("--destdir", dest="destdir", default=DEF_DESTDIR,
                      help="place to download all the results/packages")
    parser.add_option("--packages", dest="packages_file", default=None,
                      help="file to read list of packages from")
    parser.add_option("--do-sign", dest="do_sign", default=False,
                      help="enable package signing")
    parser.add_option("-q", "--quiet", dest="quiet", default=False,
                      action="store_true",
                      help="output very little to the terminal")
    parser.add_option("-f", "--front_url", dest="front_url",
                      help="copr frontend url")
    parser.add_option("--results_url", dest="results_base_url",
                      help="backend base url for built packages")

    opts, args = parser.parse_args(args)

    if not opts.builder:
        sys.stderr.write("Must specify a system to build on")
        sys.exit(1)

    if opts.packages_file and os.path.exists(opts.packages_file):
        args.extend(read_list_from_file(opts.packages_file))

    # args = list(set(args)) # poor man's 'unique' - this also changes the order
    # :(

    if not args:
        sys.stderr.write("Must specify at least one pkg to build")
        sys.exit(1)

    if not opts.chroot:
        sys.stderr.write("Must specify a mock chroot")
        sys.exit(1)

    for url in opts.repos:
        if not (url.startswith("http://") or
                url.startswith("https://") or url.startswith("file://")):

            sys.stderr.write("Only http[s] or file urls allowed for repos")
            sys.exit(1)

    if not opts.front_url:
        print("No front url was specified, exiting", file=sys.stderr)
        sys.exit(1)

    return opts, args


# FIXME
# play with createrepo run at the end of each build
# need to output the things that actually worked :)


def main(args):

    # parse args
    opts, pkgs = parse_args(args)

    if not os.path.exists(opts.destdir):
        os.makedirs(opts.destdir)

    try:
        # setup our callback
        callback = CliLogCallBack(logfn=opts.logfile, quiet=opts.quiet)
        # our mockremote instance

        class JobClass(object):
            __slots__ = ["timeout", "destdir", "chroot", "pkgs"]

        job = JobClass()
        job.timeout = opts.timeout
        job.destdir = opts.destdir
        job.chroot = opts.chroot
        job.pkgs = opts.pkgs

        mr = MockRemote(
            job=job,
            builder_host=opts.builder,
            user=opts.user,
            # cont=opts.cont,
            # recurse=opts.recurse,
            repos=opts.repos,
            do_sign=opts.do_sign,
            callback=callback,
            front_url=opts.front_url,
            results_base_url=opts.results_base_url,
        )

        # FIXMES
        # things to think about doing:
        # output the remote tempdir when you start up
        # output the number of pkgs
        # output where you're writing things to
        # consider option to sync over destdir to the remote system to use
        # as a local repo for the build
        #

        if not opts.quiet:
            print("Building {0} pkgs".format(len(pkgs)))

        mr.build_pkgs()

        if not opts.quiet:
            print("Output written to: {0}".format(opts.destdir))

    except MockRemoteError as e:
        sys.stderr.write("Error on build:\n")
        sys.stderr.write("{0}\n".format(e))
        return


if __name__ == "__main__":
    main(sys.argv[1:])
