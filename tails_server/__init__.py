from .args import get_settings
from .web import start


def main():
    settings = get_settings()
    start(settings)


if __name__ == "__main__":
    main()
