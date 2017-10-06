import os
import logging
import tempfile

log = logging.getLogger("__main__")


class Provider(object):
    def __init__(self, source_json, outdir, config):
        self.outdir = outdir
        self.config = config

        self.workdir = tempfile.mkdtemp()

        # Change home directory to workdir and create .rpmmacros there
        os.environ["HOME"] = self.workdir
        self.create_rpmmacros()

    @property
    def srpm(self):
        dest_files = os.listdir(self.outdir)
        dest_srpms = list(filter(lambda f: f.endswith(".src.rpm"), dest_files))

        if len(dest_srpms) != 1:
            log.debug("tmp_dest: {}".format(self.outdir))
            log.debug("dest_files: {}".format(dest_files))
            log.debug("dest_srpms: {}".format(dest_srpms))
            raise RuntimeError("Expected one srpm file generated.")
        return os.path.join(self.outdir, dest_srpms[0])

    def create_rpmmacros(self):
        path = os.path.join(self.workdir, ".rpmmacros")
        with open(path, "w") as rpmmacros:
            rpmmacros.write("%_disable_source_fetch 0")

    def __exit__(self, exc_type, exc_value, traceback):
        self.cleanup()

    def cleanup(self):
        try:
            shutil.rmtree(self.workdir)
        except OSError as e:
            pass
