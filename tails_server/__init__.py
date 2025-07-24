from pathlib import Path

from .args import get_settings
from .web import start
from .loadlogger import LoggingConfigurator

def configure_logging(settings):
    """Perform common app configuration."""
    # Set up logging
    log_config = settings['log_config']
    log_level = settings['log_level']
    log_file = settings['log_file']
    LoggingConfigurator.configure(
        log_config_path=log_config,
        log_level=log_level,
        log_file=log_file,
    )

def main():
    settings = get_settings()
    Path(settings["storage_path"]).mkdir(parents=True, exist_ok=True)
    configure_logging(settings)
    start(settings)


if __name__ == "__main__":
    main()
