import os

from pprint import pprint

from backend.sign import get_pubkey, sign_rpms_in_dir
from backend.mockremote import log

if __name__ == "__main__":
    user = "vgologuz3"
    prj = "copr"

    chroot_dir = "/var/lib/copr/public_html/results/vgologuz/copr/epel-6-i386/python-copr-1.48-1.fc20/"


    #print(create_user_keys(user, prj))
    from backend.mockremote import CliLogCallBack
    #cb = CliLogCallBack(logfn=pprint)
    cb = CliLogCallBack(logfn=None)
    #print(get_pubkey(user, prj, os.path.join(chroot_dir, "pubkey.gpg")))
    #print(get_pubkey(user, prj))
    sign_rpms_in_dir(user, prj, chroot_dir, cb)

