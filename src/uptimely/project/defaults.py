"""Default values for an Uptimely project."""

import pathlib
import typing

DEFAULT_PROJECT_ROOT: typing.Final = pathlib.Path(".")
DEFAULT_SRC_PATH: typing.Final = pathlib.Path("src")
DEFAULT_TEST_PATH: typing.Final = "tests"
DEFAULT_SPEC_ATTRIBUTE: typing.Final = "spec"
