from pathlib import Path

from .args import get_settings
from .logging import configure as configure_logging
from .web import start


def main():
    settings = get_settings()
    Path(settings["storage_path"]).mkdir(parents=True, exist_ok=True)
    configure_logging(
        logging_config_path=settings["log_config"], log_level=settings["log_level"]
    )
    start(settings)


if __name__ == "__main__":
    main()
