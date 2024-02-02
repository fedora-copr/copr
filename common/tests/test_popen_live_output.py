import sys
import pytest

if sys.version_info[0] >= 3:

    from copr_common.subprocess_live_output import PosixPipedProcess

    @pytest.mark.parametrize('output', ['stdout', 'stderr'])
    def test_posix_live_output_one_stream(output):
        redirect = "" if output == 'stdout' else '>&2'
        opposite = "stderr" if output == 'stdout' else 'stdout'
        proc = PosixPipedProcess([
            "sh", "-c",
            "echo {redirect} {output} ; sleep 0.2; "
            "echo {redirect} -n {output}".format(output=output, redirect=redirect)
        ])
        outs = {"stdout": "", "stderr": ""}
        for chunk, out in proc.readchunks():
            assert out != opposite
            outs[out] += chunk.decode("utf8")

        assert proc.returncode == 0
        assert proc.stopreason == 0
        assert outs[opposite] == ""
        assert outs[output] == "{output}\n{output}".format(output=output)

    def test_posix_live_output_both():
        proc = PosixPipedProcess([
            "sh", "-c",
            "echo -n output ; "
            "echo -n errout >&2 ; "
            "echo output ; "
            "echo errout >&2"
        ])
        outs = {"stdout": "", "stderr": ""}
        for chunk, out in proc.readchunks():
            outs[out] += chunk.decode("utf8")

        assert proc.returncode == 0
        assert proc.stopreason == 0
        assert not proc.has_cut()
        assert outs['stdout'] == "outputoutput\n"
        assert outs['stderr'] == "errouterrout\n"


    @pytest.mark.parametrize("dataset", [
        (["/bin/false"], 1, "", ""),
        (["/bin/true"], 0, "", ""),
    ])
    def test_posix_live_output_exit_status(dataset):
        cmd, exp_rc, exp_out, exp_err = dataset
        proc = PosixPipedProcess(cmd)
        outs = {"stdout": "", "stderr": ""}
        for chunk, out in proc.readchunks():
            outs[out] += chunk.decode("utf8")
        assert proc.returncode == exp_rc
        assert proc.stopreason == 0
        assert not proc.has_cut()
        assert outs['stdout'] == exp_out
        assert outs['stderr'] == exp_err


    def test_posix_live_output_timeout():
        cmd = ["bash", "-c", "echo ahoj; sleep 100"]
        proc = PosixPipedProcess(cmd, timeout=2, poll=0.1)
        outs = {"stdout": "", "stderr": ""}
        for chunk, out in proc.readchunks():
            outs[out] += chunk.decode("utf8")
        assert proc.timeouted()
        assert not proc.has_cut()
        assert proc.returncode == -9
        assert outs['stdout'] == "ahoj\n"
        assert outs['stderr'] == ""


    def test_posix_live_output_cut():
        cmd = ["bash", "-c", "echo aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"]
        proc = PosixPipedProcess(cmd, stdout_limit=10)
        outs = {"stdout": "", "stderr": ""}
        for chunk, out in proc.readchunks():
            outs[out] += chunk.decode("utf8")
        assert proc.returncode == 0
        assert proc.has_cut()
        assert outs['stdout'] == "aaaaaaaaaa"
        assert outs['stderr'] == ""

    def test_posix_live_output_cut_long():
        cmd = ["bash", "-c", "while :; do echo -n aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa >&2; done"]
        proc = PosixPipedProcess(cmd, stderr_limit=10)
        outs = {"stdout": "", "stderr": ""}
        for chunk, out in proc.readchunks():
            outs[out] += chunk.decode("utf8")
        assert outs['stdout'] == ""
        assert outs['stderr'] == "aaaaaaaaaa"
        assert proc.returncode == -9
        assert proc.has_cut()
