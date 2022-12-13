"""
The 'copr-cli monitor' implementation
"""

from argparse import ArgumentTypeError

from copr_cli.helpers import cli_use_output_format
from copr_cli.printers import cli_get_output_printer


DEFAULT_FIELDS = [
    "name",
    "chroot",
    "build_id",
    "state",
    "pkg_version",
]

ADDITIONAL_FIELDS = [
    "url_build_log",
    "url_backend_log",
]

ALLOWED_FIELDS = DEFAULT_FIELDS + ADDITIONAL_FIELDS + [
    "url_build"
]


def cli_monitor_action(commands, args):
    """
    Get info about the latest chroot builds for requested packages.
    """
    ownername, projectname = commands.parse_name(args.project)

    fields = None
    if args.fields:
        fields = [arg.strip() for arg in args.fields.split(",")]

        bad_fields = []
        for field in fields:
            if field in ALLOWED_FIELDS:
                continue
            bad_fields.append(field)

        if bad_fields:
            raise ArgumentTypeError(
                "Unknown field(s) specified in --fields: " +
                str(bad_fields) + ", " +
                "allowed: " + str(ALLOWED_FIELDS),
            )
    else:
        fields = DEFAULT_FIELDS

    # Package name, and chroot name are automatically in the output.
    requested_fields = list(set(fields).intersection(ADDITIONAL_FIELDS)) or None

    data = commands.client.monitor_proxy.monitor(
        ownername=ownername, projectname=projectname,
        project_dirname=args.dirname,
        additional_fields=requested_fields,
    )


    printer = cli_get_output_printer(args.output_format, fields, True)
    for package in data["packages"]:
        for chroot_name, chroot in package["chroots"].items():
            data = {
                "name": package["name"],
                "chroot": chroot_name,
            }
            if "url_build" in fields:
                data["url_build"] = commands.build_url(chroot["build_id"])
            data.update(chroot)
            data = {
                key: value
                for key, value in data.items()
                if key in fields
            }
            printer.add_data(data)
    printer.finish()


def cli_monitor_parser(subparsers):
    """
    Append "copr-cli monitor" sub-parser.
    """
    parser_monitor = subparsers.add_parser(
            "monitor",
            help="Monitor package build state",
    )
    parser_monitor.set_defaults(func=cli_monitor_action)
    parser_monitor.add_argument(
        "project", help=("Which project's packages should be listed. "
                         "Can be just a name of the project or even in format "
                         "username/project or @groupname/project."))
    parser_monitor.add_argument(
            "--dirname",
            help=("project (sub)directory name, e.g. 'foo:pr:125', "
                  "by default just 'foo' is used"))

    cli_use_output_format(parser_monitor)

    parser_monitor.add_argument(
        "--fields",
        help=(
            "A comma-separated list (ordered) of fields to be printed. "
            "Possible values: {0}.  Note that url_build* options might "
            "significantly prolong the server response time.".format(
               ", ".join(ALLOWED_FIELDS))
        ),
    )
