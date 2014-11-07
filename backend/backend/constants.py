import os

mockchain = "/usr/bin/mockchain"
# rsync path
rsync = "/usr/bin/rsync"

DEF_REMOTE_BASEDIR = "/var/tmp"
DEF_TIMEOUT = 3600
DEF_REPOS = []
DEF_CHROOT = None
DEF_USER = "mockbuilder"
DEF_DESTDIR = os.getcwd()
DEF_MACROS = {}
DEF_BUILDROOT_PKGS = ""
