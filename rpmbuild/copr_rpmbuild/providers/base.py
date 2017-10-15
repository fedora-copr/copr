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
