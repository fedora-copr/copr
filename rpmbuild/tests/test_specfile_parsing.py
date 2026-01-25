import os
import tempfile
from unittest.mock import patch, MagicMock

from copr_rpmbuild.extract_specfile_tags import get_architecture_specific_tags


def _patched_response():
    testdir = os.path.dirname(__file__)
    db = os.path.join(testdir, "testing-overrides.json")
    fake_response = MagicMock()
    with open(db, "rb") as fd:
        fake_response.content = fd.read()
        fake_response.status_code = 200

    return fake_response


@patch('copr_common.request.SafeRequest.get')
def test_extract_success(mock_get):
    mock_get.return_value = _patched_response()
    testdir = os.path.dirname(__file__)
    spec = os.path.join(testdir, "exclusive-test.spec")
    expected = {
        'rhel-10': {'exclusivearch': ['ppc64le', 'x86_64'],
                    'excludearch': ['athlon', 'x86_64']},
        'fedora-rawhide': {'exclusivearch': ['aarch64', 'x86_64'],
                           'excludearch': ['aarch64', 'athlon']}
    }
    assert get_architecture_specific_tags(spec, ["excludearch", "exclusivearch"],
                                          ["rhel-10", "fedora-rawhide"], "faked") == expected


@patch('copr_common.request.SafeRequest.get')
def test_extract_failure(mock_get):
    mock_get.return_value = _patched_response()
    testdir = os.path.dirname(__file__)
    spec = os.path.join(testdir, "exclusive-test.spec")
    mock_get.return_value = _patched_response()
    expected = {
        'fedora-rawhide': {
            'exclusivearch': [
                'xyz',
            ],
        },
        'rhel-10': {
            'exclusivearch': [
                'xyz',
            ],
        },
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        spec = os.path.join(tmp_dir, "foo.spec")
        with open(spec, "w", encoding="utf-8") as fd:
            fd.write("ExclusiveArch: xyz\n")
            fd.write("%if\n")  # syntax error
            fd.write("ExclusiveArch: abc\n")  # ignored part

        assert get_architecture_specific_tags(spec, ["excludearch",
                                                     "exclusivearch"],
                                              ["rhel-10", "fedora-rawhide"],
                                              "fake") == expected
