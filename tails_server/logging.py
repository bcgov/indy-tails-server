import logging
from io import TextIOWrapper
from logging.config import fileConfig
from typing import TextIO

import pkg_resources

DEFAULT_LOGGING_CONFIG_PATH = "tails_server.config:default_logging_config.ini"


def load_resource(path: str, encoding: str = None) -> TextIO:
    """
    Open a resource file located in a python package or the local filesystem.
    Args:
        path: The resource path in the form of `dir/file` or `package:dir/file`
    Returns:
        A file-like object representing the resource
    """
    components = path.rsplit(":", 1)
    try:
        if len(components) == 1:
            return open(components[0], encoding=encoding)
        else:
            bstream = pkg_resources.resource_stream(components[0], components[1])
            if encoding:
                return TextIOWrapper(bstream, encoding=encoding)
            return bstream
    except IOError:
        pass


def configure(
    cls, logging_config_path: str = None, log_level: str = None, log_file: str = None,
):
    """
    Configure logger.
    :param logging_config_path: str: (Default value = None) Optional path to
        custom logging config
    :param log_level: str: (Default value = None)
    """
    if logging_config_path is not None:
        config_path = logging_config_path
    else:
        config_path = DEFAULT_LOGGING_CONFIG_PATH

    log_config = load_resource(config_path, "utf-8")
    if log_config:
        with log_config:
            fileConfig(log_config, disable_existing_loggers=False)
    else:
        logging.basicConfig(level=logging.WARNING)
        logging.root.warning(f"Logging config file not found: {config_path}")

    if log_file:
        logging.root.handlers.clear()
        logging.root.handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    if log_level:
        log_level = log_level.upper()
        logging.root.setLevel(log_level)
