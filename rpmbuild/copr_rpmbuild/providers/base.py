import os
import logging


log = logging.getLogger("__main__")


class Provider(object):
    def __init__(self, source_json, workdir=None, confdirs=None):
        self.workdir = workdir
        self.resultdir = workdir
        self.confdirs = confdirs

    @property
    def srpm(self):
        dest_files = os.listdir(self.resultdir)
        dest_srpms = list(filter(lambda f: f.endswith(".src.rpm"), dest_files))

        if len(dest_srpms) != 1:
            log.debug("tmp_dest: {}".format(self.resultdir))
            log.debug("dest_files: {}".format(dest_files))
            log.debug("dest_srpms: {}".format(dest_srpms))
            raise RuntimeError("No srpm files were generated.")
        return os.path.join(self.resultdir, dest_srpms[0])
