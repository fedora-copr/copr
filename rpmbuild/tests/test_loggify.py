"""
Test the bin/copr-rpmbuild-loggify filter
"""

import os
import shutil
import subprocess
import tempfile

INPUT = """
This is \x1b\x5b\x33\x34\x6dblue\x1b\x5b\x30\x6d text
WIP progress-bar\x0dprogress-bar
trailing SO/SI/CR\x0e\x0f\r
end
"""

OUTPUT = """
This is blue text
progress-bar
trailing SO/SI/CR
end
"""


def test_loggify():
    tmpdir = tempfile.mkdtemp(prefix="copr-rpmbuild-test-loggify-")
    input_file = os.path.join(tmpdir, "input")
    output_file = os.path.join(tmpdir, "output")
    with open(input_file, "w") as fd:
        fd.write(INPUT)

    subprocess.call(
        "copr-rpmbuild-loggify < {0} > {1}".format(
            input_file, output_file,
        ),
        shell=True,
        cwd=os.path.dirname(__file__),
    )

    with open(output_file, "r") as fd:
        output = fd.read()

    assert output == OUTPUT
    shutil.rmtree(tmpdir)
