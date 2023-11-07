#! /usr/bin/python3

"""
Print a set of 'resalloc ticket-close' commands to be manually executed if there
are some tickets that deserve a manual close (because backend knows nothing
about them).

This script is using a heuristic by analyzing the `ps aux` output because we
don't track the list of tickets anywhere (only the corresponding builder knows
it's own ticket ID).  It would be risky to expect that the lists of IDs are
complete (no lock between the used_ids() and all_ids() calls).  Therefore we
take the oldest used ticket (copr can not take any older one in the future), and
then we don't suggest removing of any newer ticket ID than that one.
"""

import subprocess

from resallocserver.app import session_scope
from resallocserver.logic import QTickets

from copr_common.helpers import script_requires_user

def used_ids():
    """
    Return a set of ticket_ids that can be found in the "ps aux" output.
    """
    cmd = (
        "ps aux | "
        "grep ticket_id |"
        "sed -n 's/.*ticket_id=\\([0-9]\\+\\).*/\\1/p'"
    )
    output = subprocess.check_output(cmd, shell=True).decode("utf8")
    output = output.strip()
    tickets = set()
    for ticket_id in output.split("\n"):
        assert all(c.isdigit() for c in ticket_id)
        tickets.add(int(ticket_id))
    return tickets


def all_ids():
    """
    Return all, not yet closed ticket ids (Resalloc DB).
    """
    with session_scope() as session:
        tq = QTickets(session)
        tickets = set()
        for ticket in tq.not_closed().all():
            tickets.add(ticket.id)
    return tickets


def print_once(message):
    """
    Print the given message just once, even if called multiple times.
    """
    # get the function-static storage
    storage = getattr(print_once, "_storage", {})
    setattr(print_once, "_storage", storage)
    if message not in storage:
        print(message)
        storage[message] = True


if __name__ == "__main__":
    script_requires_user("resalloc")

    used = used_ids()

    # This is the oldest ticket that Copr Backend currently uses.
    min_used = min(used)

    all_known = all_ids()
    unknown = all_known - used

    for unknown_id in sorted(unknown):
        if unknown_id < min_used:
            print_once("These are old tickets, Copr only uses newer tickets, close them:")
            print(f"resalloc ticket-close {unknown_id}")
        else:
            print_once("These tickets are relatively new for closing blindly, double check!")
            print(f"resalloc ticket-check {unknown_id}")
