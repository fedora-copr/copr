"""
Test the SSHConnection class
"""

from copr_backend.sshcmd import SSHConnection

def test_ipv4_ipv6_rsync():
    connection = SSHConnection(
        "test", "2620:52:3:1:dead:beef:cafe:c149", config_file="something",
    )
    # pylint: disable=protected-access
    assert connection._full_source_path("/xyz") == "test@[2620:52:3:1:dead:beef:cafe:c149]:/xyz"
    connection = SSHConnection(
        "test", "192.168.0.1", config_file="something",
    )
    assert connection._full_source_path("/xyz") == "test@192.168.0.1:/xyz"
