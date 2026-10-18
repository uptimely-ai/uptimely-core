"""Standard paths and conventions for an Uptimely analytics project."""

import pathlib
import typing

CONFIG_DIR: typing.Final = pathlib.Path("config")
ANALYTICS_SOURCE_DIR: typing.Final = CONFIG_DIR / "analytics"
ANALYTICS_PYTHON_ENTRY_FILE: typing.Final = ANALYTICS_SOURCE_DIR / "analytics.py"
DEFAULT_ANALYTICS_ATTRIBUTE: typing.Final = "python_analytics"
ANALYTICS_JSON_ENTRY_FILE: typing.Final = ANALYTICS_SOURCE_DIR / "analytics.json"
COMPILER_CONFIG_FILE: typing.Final = CONFIG_DIR / "compiler.json"
ENGINE_CONFIG_FILE: typing.Final = CONFIG_DIR / "engine.json"

DATA_DIR: typing.Final = pathlib.Path("data")
FUNCTIONS_DIR: typing.Final = pathlib.Path("functions")

GENERATED_DIR: typing.Final = pathlib.Path("_generated")

ANALYTICS_OUTPUT_DIR: typing.Final = GENERATED_DIR / "analytics"
ANALYTICS_JSON_FILE: typing.Final = ANALYTICS_OUTPUT_DIR / "analytics.json"

COMPILE_OUTPUT_DIR: typing.Final = GENERATED_DIR / "compile"
EXECUTION_PLAN_FILE: typing.Final = COMPILE_OUTPUT_DIR / "execution_plan.json"

EXPLORER_OUTPUT_DIR: typing.Final = GENERATED_DIR / "explorer"
EXPLORER_INDEX_FILE: typing.Final = EXPLORER_OUTPUT_DIR / "index.html"
