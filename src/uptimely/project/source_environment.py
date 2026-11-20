"""Prepare a project's Python source environment."""

from __future__ import annotations

import pathlib
import typing

from uptimely.codebase.python import environment

from . import defaults, paths


def project_source_path(
    root: pathlib.Path, src_path: pathlib.Path | None = None
) -> typing.ContextManager[None]:
    """Make project modules importable for the duration of an operation."""
    root = root.resolve()
    source = root / defaults.DEFAULT_SRC_PATH if src_path is None else src_path
    if not source.is_absolute():
        source = root / source
    source = source.resolve()
    if src_path is not None and not source.is_dir():
        raise NotADirectoryError(f"Project source path is not a directory: {source}")

    return environment.PythonSourceEnvironment(
        root,
        source,
        module_roots=(root / paths.SPEC_SOURCE_DIR,),
        reserved_modules=("uptimely",),
    ).activate()
