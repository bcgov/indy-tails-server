import logging
from logging.config import fileConfig
from os import path

DEFAULT_LOGGING_CONFIG_PATH = path.join(
    path.dirname(path.abspath(__file__)), "config", "default_logging_config.ini"
)


class BadLogConfigError(Exception):
    pass


def configure(logging_config_path: str = None, log_level: str = None):
    if logging_config_path is not None:
        config_path = logging_config_path
    else:
        config_path = DEFAULT_LOGGING_CONFIG_PATH

    try:
        fileConfig(config_path, disable_existing_loggers=False)
    except KeyError:
        # Oddly, fileConfig raises "KeyError: 'formatters'" if file not found
        logging.root.error(f"Logging config file not found: {config_path}")
        raise BadLogConfigError()

    if log_level:
        log_level = log_level.upper()
        logging.root.setLevel(log_level)
