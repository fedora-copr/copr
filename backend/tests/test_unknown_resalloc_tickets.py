"""
Test the ./run/copr-backend-unknown-resalloc-tickets.py script
"""

import contextlib
import importlib
import io
from unittest import mock

from testlib import patch_path_run, patch_path_fake_executables, patch_getpwuid

SCRIPT_NAME = 'copr-backend-unknown-resalloc-tickets.py'
SPEC = importlib.util.spec_from_file_location("spec", "run/" + SCRIPT_NAME)
SCRIPT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT)

EXPECTED_TICKETS = {5273992, 5273994, 5273997, 5273999, 5274000, 5274329,
                    5274764, 5274768, 5274772, 5274773, 5274774, 5274775}


def main_output(ids):
    with mock.patch.object(SCRIPT, "all_ids", return_value=ids):
        f = io.StringIO()
        with contextlib.redirect_stdout(f):
            SCRIPT._main()  # pylint: disable=protected-access
            return f.getvalue()


@patch_path_run
@patch_path_fake_executables("unknown_tickets")
@patch_getpwuid("resalloc")
def test_unknown_tickets():
    # not ticket found in DB
    assert main_output({}) == "no tickets taken\n"
    assert SCRIPT.used_ids() == EXPECTED_TICKETS

    # no unused ticket
    assert main_output(EXPECTED_TICKETS) == ""

    assert main_output(EXPECTED_TICKETS | {1}) == """\
These are old tickets, Copr only uses newer tickets, close them:
resalloc ticket-close 1
"""
    assert main_output(EXPECTED_TICKETS | {6000000}) == """\
These tickets are relatively new for closing blindly, double check!
resalloc ticket-check 6000000
"""
    assert main_output(EXPECTED_TICKETS | {1, 6000000}) == """\
resalloc ticket-close 1
resalloc ticket-check 6000000
"""
