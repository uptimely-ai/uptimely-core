"""Project structure, defaults, and source environment."""

from .defaults import DEFAULT_PROJECT_ROOT, DEFAULT_SPEC_ATTRIBUTE, DEFAULT_SRC_PATH
from .paths import (
    ARTIFACTS_DIR,
    BUILD_EXECUTION_PLAN_FILE,
    BUILD_MANIFEST_FILE,
    BUILD_OUTPUT_DIR,
    BUILD_SPEC_FILE,
    COMPILER_CONFIG_FILE,
    CONFIG_DIR,
    CONFIG_FILE,
    DATA_DIR,
    EXPLORER_DATA_FILE,
    FUNCTIONS_DIR,
    RUN_MANIFEST_FILE,
    RUN_OUTPUT_DIR,
    SPEC_JSON_ENTRY_FILE,
    SPEC_PYTHON_ENTRY_FILE,
    SPEC_SOURCE_DIR,
)
from .python_imports import expose
from .spec_source import (
    JsonSpecSource,
    PythonSpecSource,
    ResolvedSpecSource,
    SpecSourceResolver,
    load_project_spec,
    load_spec_source,
)

__all__ = [
    "ARTIFACTS_DIR",
    "BUILD_EXECUTION_PLAN_FILE",
    "BUILD_MANIFEST_FILE",
    "BUILD_OUTPUT_DIR",
    "BUILD_SPEC_FILE",
    "COMPILER_CONFIG_FILE",
    "CONFIG_DIR",
    "CONFIG_FILE",
    "DATA_DIR",
    "DEFAULT_PROJECT_ROOT",
    "DEFAULT_SPEC_ATTRIBUTE",
    "DEFAULT_SRC_PATH",
    "EXPLORER_DATA_FILE",
    "FUNCTIONS_DIR",
    "JsonSpecSource",
    "PythonSpecSource",
    "RUN_MANIFEST_FILE",
    "RUN_OUTPUT_DIR",
    "ResolvedSpecSource",
    "SPEC_JSON_ENTRY_FILE",
    "SPEC_PYTHON_ENTRY_FILE",
    "SPEC_SOURCE_DIR",
    "SpecSourceResolver",
    "load_project_spec",
    "load_spec_source",
    "expose",
]
