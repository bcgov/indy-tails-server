"""Logging Configurator for tails server."""

import io
import logging
import os
import sys
from importlib import resources
from logging.config import dictConfigClass
from typing import Optional

import yaml

sys.path.insert(1, os.path.realpath(os.path.dirname(__file__)) + "/config")

LOGGER = logging.getLogger(__name__)


def load_resource(path: str, encoding: Optional[str] = None):
    """Open a resource file located in a python package or the local filesystem.

    Args:
        path (str): The resource path in the form of `dir/file` or `package:dir/file`
        encoding (str, optional): The encoding to use when reading the resource file.
            Defaults to None.

    Returns:
        file-like object: A file-like object representing the resource
    """
    components = path.rsplit(":", 1)
    try:
        if len(components) == 1:
            # Local filesystem resource
            return open(components[0], encoding=encoding)
        else:
            # Package resource
            package, resource = components
            bstream = resources.files(package).joinpath(resource).open("rb")
            if encoding:
                return io.TextIOWrapper(bstream, encoding=encoding)
            return bstream
    except IOError:
        LOGGER.warning(f"Resource not found: {path}")
        return None


def dictConfig(config, new_file_path=None):
    """Custom dictConfig, https://github.com/python/cpython/blob/main/Lib/logging/config.py."""
    if new_file_path:
        config["handlers"]["rotating_file"]["filename"] = f"{new_file_path}"
    dictConfigClass(config).configure()


class LoggingConfigurator:
    """Utility class used to configure logging and print an informative start banner."""

    @classmethod
    def configure(
        cls, log_config_path: Optional[str] = None, log_level: Optional[str] = None
    ):
        """Configure logger.

        :param logging_config_path: str: (Default value = None) Optional path to
            custom logging config

        :param log_level: str: (Default value = None)
        """

        cls._configure_logging(log_config_path=log_config_path, log_level=log_level)

    @classmethod
    def _configure_logging(cls, log_config_path, log_level):
        # Setup log config and log file if provided
        cls._setup_log_config_file(log_config_path)

        # Set custom log level
        if log_level:
            logging.root.setLevel(log_level.upper())

    @classmethod
    def _setup_log_config_file(cls, log_config_path):
        log_config, is_dict_config = cls._load_log_config(log_config_path)

        # Setup config
        if not log_config:
            logging.basicConfig(level=logging.WARNING)
            logging.root.warning(f"Logging config file not found: {log_config_path}")
        elif is_dict_config:
            dictConfig(log_config)

    @classmethod
    def _load_log_config(cls, log_config_path):
        if ".yml" in log_config_path or ".yaml" in log_config_path:
            with open(log_config_path, "r") as stream:
                return yaml.safe_load(stream), True
        return load_resource(log_config_path, "utf-8"), False
