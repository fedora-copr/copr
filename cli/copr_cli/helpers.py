"""
Helpers for the 'copr-cli' command.
"""

output_format_help = """
Set the formatting style. We recommend using json, which prints the required data
in json format. The text format prints the required data in a column, one piece of
information per line. The text-row format prints all information separated
by a space on a single line.
"""

def cli_use_output_format(parser, default='json'):
    """
    Add '--output-format' option to given parser.
    """
    parser.add_argument(
        "--output-format",
        choices=["text", "json", "text-row"],
        help=output_format_help,
        default=default,
    )


def print_project_info(project):
    """Prints info about project"""
    print("Name: {0}".format(project.name))
    print("  Description: {0}".format(project.description))
    if project.chroot_repos:
        print("  Repo(s):")
        for name, url in project.chroot_repos.items():
            print("    {0}: {1}".format(name, url))
    if project.additional_repos:
        additional_repos_str = " ".join(project.additional_repos)
        print("  Additional repo: {0}".format(additional_repos_str))
    print("")
