import logging
from ..helpers import run_cmd


log = logging.getLogger("__main__")


class RubyGemsProvider(object):
    def __init__(self, source_json, workdir=None, confdirs=None):
        self.workdir = workdir
        self.confdirs = confdirs
        self.gem_name = source_json["gem_name"]

    def run(self):
        result = self.produce_srpm()
        if "Empty tag: License" in result.stderr:
            raise RuntimeError("\n".join([
                result.stderr,
                "Not specifying a license means all rights are reserved;"
                "others have no rights to use the code for any purpose.",
                "See http://guides.rubygems.org/specification-reference/#license="]))

    def produce_srpm(self):
        cmd = ["gem2rpm", self.gem_name, "--srpm", "-C", self.workdir, "--fetch"]
        return run_cmd(cmd)
