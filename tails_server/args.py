"""Command line option parsing."""

import argparse


PARSER = argparse.ArgumentParser(description="Runs the server.")


PARSER.add_argument(
    "--host",
    type=str,
    required=False,
    dest="host",
    metavar="<host>",
    help="Specify the host for which to accept connections.",
)

PARSER.add_argument(
    "--port",
    type=str,
    required=False,
    dest="port",
    metavar="<port>",
    help="Specify the port on which to accept connections.",
)


def get_settings():
    """Convert command line arguments to a settings dictionary."""

    args = PARSER.parse_args()
    settings = {}

    settings["host"] = args.host
    settings["port"] = args.port

    return settings
