#! /usr/bin/python3

import os
import sys
import requests
# pylint: disable=wrong-import-position
sys.path.append("/usr/share/copr/coprs_frontend/")
from coprs.models import User
from coprs import app

DATADIR = "/var/lib/copr/data/"

TEMPLATE = """\
[copr-cli]
username = {username}
login = {login}
token = {token}
copr_url = https://{host}
"""


def get_host():
    """
    What is our public IPv4?
    """
    requests.packages.urllib3.util.connection.HAS_IPV6 = False
    out = requests.get("https://ifconfig.me", timeout=30)
    return out.content.decode("utf-8")


def _main():
    username = sys.argv[1]
    users_dir = os.path.join(DATADIR, "manually-created-user-tokens")
    try:
        os.mkdir(users_dir, mode=0o700)
    except FileExistsError:
        pass
    token_file = os.path.join(users_dir, username)
    user = User.query.filter_by(username=username).first()
    token = TEMPLATE.format(
        username=username,
        login=user.api_login,
        token=user.api_token,
        host=get_host(),
    )
    with open(token_file, "w", encoding="utf-8") as fd:
        fd.write(token)
        os.fchmod(fd.fileno(), 0o600)


if __name__ == "__main__":
    with app.app_context():
        _main()
