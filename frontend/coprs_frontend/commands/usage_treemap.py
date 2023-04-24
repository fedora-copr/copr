"""
Usage treemap
"""

import os
from datetime import datetime, timedelta

import click
import pygal
from coprs import app, models


@click.command()
@click.option("--dest", "-D", required=True, help="Result directory")
@click.option("--days", default=91, help="Ignore any builds older than this")
def usage_treemap(dest, days):
    """
    Generate usage heatmap
    """
    since = datetime.today() - timedelta(days=days)

    # Prepare the data for graph generation, this will take some time
    # We also sort the data first, so the graph appears less random and, so
    # that our legend is ordered
    build_chroots = get_build_chroots(since).all()
    data = count_builds_per_user(build_chroots)
    data = dict(sorted(data.items(), key=lambda item: item[1], reverse=True))
    grouped = grouped_data_per_team(data)

    # Make sure the dest directory exists
    os.makedirs(dest, exist_ok=True)

    # Generate graphs
    stamp = datetime.now().strftime("%Y-%m-%d")
    tuples = [("usage_treemap", data), ("usage_treemap_grouped", grouped)]

    for key, value in tuples:
        title = "Copr {}\n{} - {}".format(
            key.replace("_", " "),
            since.strftime("%Y-%m-%d"),
            stamp)
        name = "{}-{}.svg".format(stamp, key)
        path = os.path.join(dest, name)
        generate_graph(title, value, path)
        print("Created: {}".format(path))


def get_build_chroots(since):
    """
    Get all `BuildChroot` instances since a given timestamp
    """
    query = (
        models.BuildChroot.query
        .join(models.Build)
        .join(models.Copr)
        .filter(models.Build.submitted_on > since.timestamp()))
    return query


def count_builds_per_user(build_chroots):
    """
    For every user and group, count how many of the `build_chroots` they own.
    We don't count how many builds `user1` submitted but rather how many
    builds happened in his projects.
    """
    users = {}
    for chroot in build_chroots:
        name = chroot.build.copr.owner_name
        users.setdefault(name, 0)
        users[name] += 1
    return users


def grouped_data_per_team(data):
    """
    Some users work together in a team. Let's clump their data together.
    """
    # The config option is user-friendly for configuration but not useful for
    # searching. Let's transform it from e.g.
    #   {"CPT": ["frostyx", "praiskup"], "Packit": ["ttomecek"]}
    # to
    #   {"frostyx": "CPT", "praiskup": "CPT", "ttomecek": "Packit"}
    teams = {}
    for name, members, in app.config["USAGE_TREEMAP_TEAMS"].items():
        for member in members:
            teams[member] = name

    # And finally generate the result dict, e.g.
    # {"CPT": {"frostyx": 123, "praiskup": 345}, "Packit": {"ttomecek": 678}}
    result = {}
    for user, value in data.items():
        key = teams.get(user, user)
        result.setdefault(key, {})
        result[key][user] = value
    return result


def generate_graph(title, data, path):
    """
    Generate a treemap from our data
    """
    treemap = pygal.Treemap(
        title=title,
        height=800,
        width=1800,
        explicit_size=True,
        value_formatter="{} builds".format,
    )

    for name, value in data.items():
        # This condition is needed for rendering non-grouped data
        if isinstance(value, int):
            value = {name: value}
        items = [{"value": v, "label": k} for k, v in value.items()]
        treemap.add(name, items)
    treemap.render_to_file(path)
