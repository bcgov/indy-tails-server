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
    type=int,
    required=False,
    dest="port",
    metavar="<port>",
    help="Specify the port on which to accept connections.",
)

PARSER.add_argument(
    "--log-level",
    dest="log_level",
    default="DEBUG",
    choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    help="Python3 logging library level",
)

PARSER.add_argument(
    "--log-config",
    dest="log_config",
    default="/logging/config.yml",
    help="Specifies a custom logging configuration file",
)

PARSER.add_argument(
    "--storage-path",
    type=str,
    required=True,
    dest="storage_path",
    metavar="<storage_path>",
    help="Specify the path to store files.",
)


def get_settings():
    """Convert command line arguments to a settings dictionary."""

    args = PARSER.parse_args()
    settings = {}

    settings["host"] = args.host
    settings["port"] = args.port

    settings["log_config"] = args.log_config
    settings["log_level"] = args.log_level

    settings["storage_path"] = args.storage_path

    return settings
