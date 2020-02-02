import os
import logging
import tempfile
import shutil
from ..helpers import string2list

log = logging.getLogger("__main__")


class Provider(object):
    def __init__(self, source_json, outdir, config):
        self.outdir = outdir
        self.config = config

        self.workdir = tempfile.mkdtemp(prefix="copr-rpmbuild-")

        # Change home directory to workdir and create .rpmmacros there
        os.environ["HOME"] = self.workdir
        self.create_rpmmacros()

    def create_rpmmacros(self):
        path = os.path.join(self.workdir, ".rpmmacros")
        with open(path, "w") as rpmmacros:
            rpmmacros.write("%_disable_source_fetch 0\n")
            enabled_protocols = string2list(self.config.get("main", "enabled_source_protocols"))
            rpmmacros.write("%__urlhelper_localopts --proto -all,{0}\n"
                            .format(','.join(["+"+protocol for protocol in enabled_protocols])))

    def __del__(self):
        self.cleanup()

    def cleanup(self):
        try:
            shutil.rmtree(self.workdir)
        except OSError as e:
            pass
