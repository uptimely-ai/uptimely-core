"""Standard paths and conventions for an Uptimely analytics project."""

import pathlib
import typing

CONFIG_DIR: typing.Final = pathlib.Path("config")
SPEC_SOURCE_DIR: typing.Final = pathlib.Path("spec")
SPEC_PYTHON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.py"
SPEC_JSON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.json"
COMPILER_CONFIG_FILE: typing.Final = CONFIG_DIR / "compiler.json"
CONFIG_FILE: typing.Final = pathlib.Path("uptimely.toml")

DATA_DIR: typing.Final = pathlib.Path("data")
FUNCTIONS_DIR: typing.Final = pathlib.Path("functions")

ARTIFACTS_DIR: typing.Final = pathlib.Path("artifacts")
BUILD_LOCK_FILE: typing.Final = ARTIFACTS_DIR / ".build.lock"

RUN_OUTPUT_DIR: typing.Final = ARTIFACTS_DIR / "run"
RUN_MANIFEST_FILE: typing.Final = RUN_OUTPUT_DIR / "run.json"
TEST_OUTPUT_DIR: typing.Final = ARTIFACTS_DIR / "test"
TEST_CASES_DIR: typing.Final = TEST_OUTPUT_DIR / "cases"
TEST_REPORT_FILE: typing.Final = TEST_OUTPUT_DIR / "test.json"

BUILD_OUTPUT_DIR: typing.Final = ARTIFACTS_DIR / "build"
BUILD_MANIFEST_FILE: typing.Final = BUILD_OUTPUT_DIR / "build.json"
BUILD_SPEC_FILE: typing.Final = BUILD_OUTPUT_DIR / "spec.json"
BUILD_EXECUTION_PLAN_FILE: typing.Final = BUILD_OUTPUT_DIR / "plan.json"
EXPLORER_DATA_FILE: typing.Final = BUILD_OUTPUT_DIR / "explorer.json"
