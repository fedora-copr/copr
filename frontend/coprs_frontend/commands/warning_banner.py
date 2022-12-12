"""
Command for managing warning banner on the top of frontend page.
"""


import os
import sys
from pathlib import Path

import click
from jinja2 import Template

from coprs.constants import BANNER_LOCATION


@click.command()
@click.option("--outage_time", "-o", default=None, help="start time of the outage")
@click.option("--ticket", "-t", default=None, help="fedora infra ticket ID")
@click.option("--rest", default=None, help="additional code")
@click.option("--remove", is_flag=True, show_default=True, default=False, help="removes banner")
def warning_banner(outage_time, ticket, rest, remove):
    """
    Adds a banner to Copr's frontend page with outage warning. `outage_time` or `rest` is required.

     In case you need to schedule regular outage, fill in only `outage_time` and `ticket`. In case
    you need to add something else, please use the `rest` parameter to dump to warning banner
    some additional information. This can be just some text or html code.
     `rest` parameter can be used as a standalone option just for showing some warning banner
    with specific information. It can be also piece of HTML code.
    """
    if remove:
        if outage_time or ticket or rest:
            print(
                "Error: can't remove banner with `outage_time` or `ticket` or `rest`",
                file=sys.stderr,
            )
            return

        if os.path.exists(BANNER_LOCATION):
            os.remove(BANNER_LOCATION)
            return

    if outage_time is None and rest is None:
        print("Error: `outage_time` or `rest` should be present.", file=sys.stderr)
        return

    with open(BANNER_LOCATION, "w", encoding="UTF-8") as banner:
        banner_path_template = Path(__file__).parent / "../coprs/templates/banner-include.html"
        with banner_path_template.open() as banner_template:
            template = Template(banner_template.read())
            banner.write(template.render(outage_time=outage_time, ticket=ticket, rest=rest))
