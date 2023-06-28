"""
Generate failed to succeeded stats
"""

import os
from datetime import datetime

import click
import pygal
from coprs import models


@click.command()
@click.option("--dest", "-D", required=True, help="Result directory")
def failed_to_succeeded_stats(dest):
    """
    Generate failed to succeeded stats
    """
    print("Please wait, this will take at least 20 minutes.")
    categories = {
        "immediately": 0,
        "seconds": 0,
        "minutes": 0,
        "hours": 0,
        "days": 0,
        "weeks": 0,
    }
    tuples = failed_to_succeeded_tuples()
    for failed, succeeded in tuples:
        delta = datetime.fromtimestamp(succeeded) \
            - datetime.fromtimestamp(failed)
        categories[delta_to_category(delta)] += 1

    os.makedirs(dest, exist_ok=True)
    path = os.path.join(dest, "failed-to-succeeded-stats.svg")
    generate_graph(categories, path)
    print("Created: {0}".format(path))


def get_builds():
    """
    Return list of all builds
    """
    query = (
        models.Build.query
        .join(models.Package)
        .join(models.Copr)
        .order_by(models.Build.id)
    )

    # Only recent builds
    # start = datetime(2022, 1, 1).timestamp()
    # end = datetime(2023, 1, 1).timestamp()
    # query = (query
    #          .filter(models.Build.submitted_on >= start)
    #          .filter(models.Build.submitted_on <= end))

    # Packit user
    # query = query.filter(models.Copr.user_id==5576)

    # For faster development
    # query = query.limit(1000)

    return query.all()


def builds_per_package():
    """
    Return a `dict` where keys are package IDs and values are lists
    of all their builds.
    """
    builds = get_builds()
    result = {}
    for build in builds:
        result.setdefault(build.package_id, [])
        result[build.package_id].append(build)
    return result


def failed_to_succeeded_tuples():
    """
    Return a list of tuples. First value of each tuple is when the package
    failed, and the second value is when it succeeded.
    """
    tuples = []
    for builds in builds_per_package().values():
        if len(builds) <= 1:
            # This package has only one build
            # Not dealing with this now.
            continue

        failed = None
        succeeded = None

        for build in builds:
            if not build.ended_on:
                continue

            if build.state == "failed" and not failed:
                failed = build

            elif build.state == "succeeded" and failed:
                succeeded = build

            if failed and succeeded:
                assert failed.id < succeeded.id
                tuples.append((failed.ended_on, succeeded.ended_on))
                failed = None
                succeeded = None
    return tuples


def delta_to_category(delta):
    """
    Convert timedelta into a custom time category
    """
    seconds = delta.total_seconds()
    if seconds < 0:
        return "immediately"
    if seconds < 60:
        return "seconds"
    if seconds < 60 * 60:
        return "minutes"
    if seconds < 60 * 60 * 24:
        return "hours"
    if seconds < 60 * 60 * 24 * 7:
        return "days"
    return "weeks"


def generate_graph(data, path):
    """
    Generate graph from the data
    """
    title = "How long before devs submit a successfull package after a failure?"
    chart = pygal.Bar(
        title=title,
        print_values=True,
        legend_at_bottom=True,
    )
    for key, value in data.items():
        label = label_for_group(key)
        chart.add(label, value)
    chart.render_to_file(path)
    return path


def label_for_group(key):
    """
    User-friendly labels for the graph
    """
    if key == "immediately":
        return "Before it finished"
    return key.capitalize()
