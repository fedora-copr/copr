"""
Copr enhanced tito.builder.Bulider variant
"""

import os
import urllib.request

from tito.builder import Builder
from tito.common import info_out
from tito.compat import getoutput


class CustomBuilder(Builder):
    """
    Download Copy extra https:// %{SOURCEX} into the SOURCE folder.
    """

    def copy_extra_sources(self):
        # C&P from tito/builder.main.py
        cmd = "spectool -S '%s' --define '_sourcedir %s' | awk '{print $2}'"\
            % (self.spec_file, self.start_dir)
        sources = getoutput(cmd).split("\n")

        for source in sources[1:]:
            if not source.startswith("https://"):
                # so far we don't have local sources in copr project
                continue

            target = os.path.join(
                self.rpmbuild_sourcedir,
                os.path.basename(source),
            )

            # TODO: check md5sum somehow
            info_out("Downloading %s into %s" % (source, target))
            urllib.request.urlretrieve(source, target)
            self.sources.append(target)
