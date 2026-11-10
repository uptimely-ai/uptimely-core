"""Standard paths and conventions for an Uptimely analytics project."""

import pathlib
import typing

CONFIG_DIR: typing.Final = pathlib.Path("config")
SPEC_SOURCE_DIR: typing.Final = pathlib.Path("spec")
SPEC_PYTHON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.py"
DEFAULT_SPEC_ATTRIBUTE: typing.Final = "python_spec"
SPEC_JSON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.json"
COMPILER_CONFIG_FILE: typing.Final = CONFIG_DIR / "compiler.json"
CONFIG_FILE: typing.Final = CONFIG_DIR / "config.json"

DATA_DIR: typing.Final = pathlib.Path("data")
FUNCTIONS_DIR: typing.Final = pathlib.Path("functions")

GENERATED_DIR: typing.Final = pathlib.Path("_generated")

EXPLORER_DATA_FILE: typing.Final = GENERATED_DIR / "explorer.json"

RUN_OUTPUT_DIR: typing.Final = GENERATED_DIR / "run"
RUN_MANIFEST_FILE: typing.Final = RUN_OUTPUT_DIR / "run.json"

BUILD_OUTPUT_DIR: typing.Final = GENERATED_DIR / "build"
BUILD_MANIFEST_FILE: typing.Final = BUILD_OUTPUT_DIR / "build.json"
BUILD_SPEC_FILE: typing.Final = BUILD_OUTPUT_DIR / "spec.json"
BUILD_EXECUTION_PLAN_FILE: typing.Final = BUILD_OUTPUT_DIR / "execution_plan.json"
