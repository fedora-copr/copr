import os
import logging


log = logging.getLogger("__main__")


class Provider(object):
    def __init__(self, source_json, workdir=None, confdirs=None):
        self.workdir = workdir
        self.resultdir = workdir
        self.confdirs = confdirs

        # Change home directory to workdir and create .rpmmacros there
        if self.workdir:
            os.environ["HOME"] = self.workdir
            self.create_rpmmacros()

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

    def touch_sources(self):
        # Create an empty sources file to get rid of
        # "sources file doesn't exist. Source files download skipped."
        path = os.path.join(self.workdir, "sources")
        if not os.path.exists(path):
            open(path, "w").close()

    def create_rpmmacros(self):
        path = os.path.join(self.workdir, ".rpmmacros")
        with open(path, "w") as rpmmacros:
            rpmmacros.write("%_disable_source_fetch 0")

