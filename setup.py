"""Module setup."""

import os
import runpy

from setuptools import find_packages, setup

PACKAGE_NAME = "tails_server"
version_meta = runpy.run_path("./{}/version.py".format(PACKAGE_NAME))
VERSION = version_meta["__version__"]


with open(os.path.abspath("./README.md"), "r") as fh:
    long_description = fh.read()


def parse_requirements(filename):
    """Load requirements from a pip requirements file."""
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith("#")]


if __name__ == "__main__":
    setup(
        name=PACKAGE_NAME,
        version=VERSION,
        long_description=long_description,
        long_description_content_type="text/markdown",
        url="https://github.com/nrempel/tails-server",
        packages=find_packages(),
        include_package_data=True,
        package_data={"tails_server": ["requirements.txt"]},
        install_requires=parse_requirements("requirements.txt"),
        tests_require=parse_requirements("requirements.dev.txt"),
        python_requires=">=3.7.0",
        classifiers=[
            "Programming Language :: Python :: 3",
            "Programming Language :: Python :: 3.7",
            "License :: OSI Approved :: Apache Software License",
            "Operating System :: OS Independent",
        ],
        scripts=["bin/tails-server"],
    )
