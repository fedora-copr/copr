#!/usr/bin/env python3

import subprocess
import argparse
import os
import pwd
import time
import shutil
import sys

parser = argparse.ArgumentParser(description='Remove failed and obsolete succeeded builds (with the associated packages) from a copr repository. '+
                                 'The build directories should belong to `copr` user and contain `build.info`, `success` or `fail` files, otherwise nothing gets deleted. '+
                                 'The repository needs to be recreated manually afterwards with createrepo.')
parser.add_argument('path', action='store',
                   help='local path to a copr repository')
parser.add_argument('--days', type=int, action='store', default=0,
                   help='only remove failed/obsoleted builds older than DAYS')
parser.add_argument('--failed', dest='removeobsoleted', action='store_false',
                   help='only remove failed builds (keep obsoleted)')
parser.add_argument('--obsoleted', dest='removefailed', action='store_false',
                   help='only remove obsoleted builds (keep failed)')
parser.add_argument('--disableusercheck', dest='usercheckenabled', action='store_false',
                   help='do not check if the build directories belong to user `copr`')
parser.add_argument('-v', '--version', action='version', version='1.2',
                   help='print program version and exit')

args = parser.parse_args()

def get_owner(path):
    return pwd.getpwuid(os.stat(path).st_uid).pw_name

def get_builds():
    """
    Get all directories (absolute paths to them) with built rpms that satisfy given command-line criteria.
    """
    failed = []
    succeeded = []
    for basename in os.listdir(args.path):
        dir_name = os.path.abspath(os.path.join(args.path, basename))
        if not os.path.isdir(dir_name):
            continue
        if not os.path.isfile(os.path.join(dir_name, 'build.info')):
            continue
        if time.time() - os.path.getmtime(dir_name) <= args.days * 24 * 3600:
            continue
        if args.usercheckenabled and get_owner(dir_name) != 'copr':
            print('directory {} does not belong to `copr` user...skipping'.format(dir_name), file=sys.stderr)
            continue
        if os.path.isfile(os.path.join(dir_name, 'success')):
            succeeded.append(dir_name)
        if os.path.isfile(os.path.join(dir_name, 'fail')):
            failed.append(dir_name)
    return (failed, succeeded)

def get_latest_packages():
    """
    Get paths to the latest packages in the repository.
    """
    cmd = [ #TODO: use non-deprecated dnf repoquery when bz#1292475 is solved
        'repoquery',
        '--repofrompath=query,'+os.path.abspath(args.path),
        '--repoid=query',
        '-a',
        '--location'
    ]
    repoquery = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr= subprocess.PIPE)
    (stdout, stderr) = repoquery.communicate()
    if repoquery.returncode != 0:
        print("repoquery to get the lastest packages was not successful. Exiting.", file=sys.stderr)
        sys.exit(1)
    package_paths = stdout.decode(encoding='utf-8').split()
    return package_paths

if __name__ == '__main__':
    failed, succeeded = get_builds()

    if args.removefailed:
        print('Removing failed builds...')
        counter = 0
        for dir_name in failed:
            shutil.rmtree(dir_name)
            counter += 1
        print ('- {} failed builds removed'.format(counter))

    if args.removeobsoleted:
        print('Removing obsoleted builds...')
        package_paths = get_latest_packages()
        counter = 0
        for dir_name in succeeded:
            is_latest_build = False
            for package_path in package_paths:
                if dir_name in package_path:
                    is_latest_build = True
                    break
            if not is_latest_build:
                shutil.rmtree(dir_name)
                counter += 1
        print ('- {} obsoleted builds removed'.format(counter))
