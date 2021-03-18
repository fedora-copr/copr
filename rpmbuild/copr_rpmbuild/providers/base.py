import os
import errno
import logging
import tempfile
from ..helpers import string2list

log = logging.getLogger("__main__")


class Provider(object):
    def __init__(self, source_dict, outdir, config):
        self.source_dict = source_dict
        self.outdir = outdir
        self.config = config

        self.workdir = os.path.join(outdir, "obtain-sources")
        try:
            os.mkdir(self.workdir)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise

        # Change home directory to workdir and create .rpmmacros there
        os.environ["HOME"] = self.workdir
        self.create_rpmmacros()
        self.init_provider()

    def init_provider(self):
        """
        Additional configuration stuff specific to a concrete provider.
        Automatically called by __init__(), and it is _optional_, therefore we
        don't raise NotImplementedError in Provider.init_provider() parent.
        """

    def create_rpmmacros(self):
        path = os.path.join(self.workdir, ".rpmmacros")
        with open(path, "w") as rpmmacros:
            rpmmacros.write("%_disable_source_fetch 0\n")
            enabled_protocols = string2list(self.config.get("main", "enabled_source_protocols"))
            rpmmacros.write("%__urlhelper_localopts --proto -all,{0}\n"
                            .format(','.join(["+"+protocol for protocol in enabled_protocols])))

    def produce_srpm(self):
        """
        Using the TASK dict and the CONFIG, generate a source RPM in the
        RESULTDIR.  Each method needs to override this one.
        """
        raise NotImplementedError
