"""
copr-frontend eol-lifeless-rolling-chroots command
"""

import click
from coprs.logic.outdated_chroots_logic import OutdatedChrootsLogic

@click.command()
def eol_lifeless_rolling_chroots():
    """
    Go through all rolling CoprChroots and check whether they shouldn't be
    scheduled for future removal.
    """
    OutdatedChrootsLogic.trigger_rolling_eol_policy()
