import os
import re
import logging
from jinja2 import Environment, FileSystemLoader
from ..helpers import run_cmd
from .base import Provider

try:
    from urllib.parse import urlparse, urljoin
except ImportError:
    from urlparse import urlparse, urljoin


log = logging.getLogger("__main__")


class DistGitProvider(Provider):
    def __init__(self, source_json, workdir=None, confdirs=None):
        super(DistGitProvider, self).__init__(source_json, workdir, confdirs)
        self.clone_url = source_json["clone_url"]
        self.branch = source_json["branch"]

    @property
    def resultdir(self):
        return os.path.join(self.workdir, "repo")

    @resultdir.setter
    def resultdir(self, value):
        pass

    def run(self):
        repodir = os.path.join(self.workdir, "repo")
        result = self.clone(repodir)
        log.info(result)

        cfg = self.render_rpkg_template()
        log.info(cfg)

        config_path = os.path.join(self.workdir, "rpkg.conf")
        f = open(config_path, "w+")
        f.write(cfg)
        f.close()

        if self.branch:
            self.checkout(self.branch, repodir)

        module_name = self.module_name(self.clone_url)
        result = self.produce_srpm(config_path, module_name, repodir)
        log.info(result)

    def clone(self, repodir):
        cmd = ["git", "clone", self.clone_url, repodir]
        return run_cmd(cmd)

    def checkout(self, branch, repodir):
        #cmd = ["git", "checkout", branch]
        # FIXME: checkouting detaches HEAD and pyrpkg
        # is then unable to read out the current branch
        # and complains when downloading sources to make srpm.
        # Use this ugliness for the time being.
        try:
            cmd = ["git", "reset", "--hard", branch]
            return run_cmd(cmd, cwd=repodir)
        except Exception as e:
            log.exception(str(e))

        cmd = ["git", "checkout", branch]
        return run_cmd(cmd, cwd=repodir)


    def render_rpkg_template(self):
        jinja_env = Environment(loader=FileSystemLoader(self.confdirs))
        template = jinja_env.get_template("rpkg.conf.j2")
        parse = urlparse(self.clone_url)
        distgit_domain = parse.netloc
        return template.render(distgit_domain=distgit_domain, scheme=parse.scheme)

    def module_name(self, url):
        parse = urlparse(url)
        return re.sub(".git$", "", re.sub("^/c?git/", "", parse.path))

    def produce_srpm(self, config, module_name, repodir):
        cmd = ["rpkg", "--config", config, "--module-name", module_name, "srpm"]
        return run_cmd(cmd, cwd=repodir)
