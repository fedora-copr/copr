DEBUG = False

PHRASES_DIR = "/var/lib/copr-keygen/phrases/"
GPG_BINARY = "/bin/gpg2"
# TODO: rename to GPG_HOMEDIR
GNUPG_HOMEDIR = "/var/lib/copr-keygen/gnupg"

GPG_KEY_LENGTH = 2048
GPG_EXPIRE = "5y"

LOG_DIR = "/var/log/copr-keygen"
import logging
LOG_LEVEL = logging.INFO
