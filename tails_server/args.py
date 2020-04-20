"""Command line option parsing."""

import argparse


PARSER = argparse.ArgumentParser(description="Runs the server.")


PARSER.add_argument(
    "--genesis-url",
    type=str,
    dest="genesis_url",
    metavar="<genesis-url>",
    help="Specify a url from which to fetch the genesis transactions",
)


def parse_args(args):
    """Parse command line arguments and return the collection."""
    return PARSER.parse_args()


def get_settings():
    """Convert command line arguments to a settings dictionary."""

    args = parse_args()
    settings = {}

    if args.genesis_url:
        settings["ledger.genesis_url"] = args.genesis_url

    return settings
