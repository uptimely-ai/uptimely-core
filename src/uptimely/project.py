"""Standard paths and conventions for an Uptimely analytics project."""

import pathlib
import typing

CONFIG_DIR: typing.Final = pathlib.Path("config")
SPEC_SOURCE_DIR: typing.Final = CONFIG_DIR / "spec"
SPEC_PYTHON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.py"
DEFAULT_SPEC_ATTRIBUTE: typing.Final = "python_spec"
SPEC_JSON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.json"
COMPILER_CONFIG_FILE: typing.Final = CONFIG_DIR / "compiler.json"
ENGINE_CONFIG_FILE: typing.Final = CONFIG_DIR / "engine.json"

DATA_DIR: typing.Final = pathlib.Path("data")
FUNCTIONS_DIR: typing.Final = pathlib.Path("functions")

GENERATED_DIR: typing.Final = pathlib.Path("_generated")

SPEC_OUTPUT_DIR: typing.Final = GENERATED_DIR / "spec"
SPEC_JSON_FILE: typing.Final = SPEC_OUTPUT_DIR / "spec.json"

COMPILE_OUTPUT_DIR: typing.Final = GENERATED_DIR / "compile"
EXECUTION_PLAN_FILE: typing.Final = COMPILE_OUTPUT_DIR / "execution_plan.json"

EXPLORER_OUTPUT_DIR: typing.Final = GENERATED_DIR / "explorer"
EXPLORER_INDEX_FILE: typing.Final = EXPLORER_OUTPUT_DIR / "index.html"
