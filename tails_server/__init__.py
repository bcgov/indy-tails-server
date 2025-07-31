import logging
from pathlib import Path

from .args import get_settings
from .loadlogger import LoggingConfigurator
from .web import start

LOGGER = logging.getLogger(__name__)


def configure_logging(settings):
    """Perform logging configuration."""
    log_config = settings["log_config"]
    log_level = settings["log_level"]

    try:
        LoggingConfigurator.configure(log_config_path=log_config, log_level=log_level)

    except Exception as e:
        raise Exception("Logger configuration failed: ", e)


def main():
    settings = get_settings()
    Path(settings["storage_path"]).mkdir(parents=True, exist_ok=True)
    configure_logging(settings)
    start(settings)


if __name__ == "__main__":
    main()
