from pathlib import Path

from .args import get_settings
from .web import start


def main():
    settings = get_settings()
    Path(settings["storage_path"]).mkdir(parents=True, exist_ok=True)
    start(settings)


if __name__ == "__main__":
    main()
