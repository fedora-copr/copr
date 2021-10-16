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
