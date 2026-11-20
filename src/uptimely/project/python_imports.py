"""Set up temporary Python imports using an Uptimely project's layout."""

from __future__ import annotations

import pathlib
import typing

from uptimely.codebase.python import imports

from . import defaults, paths


def resolve_src_path(root: pathlib.Path, src_path: pathlib.Path | None = None) -> pathlib.Path:
    """Resolve a project's Python source directory.

    Args:
        root: Uptimely project root.
        src_path: Explicit source path, or ``None`` for the default ``src`` path.

    Returns:
        The absolute Python source path.
    """
    root = root.resolve()
    source = root / defaults.DEFAULT_SRC_PATH if src_path is None else pathlib.Path(src_path)
    if not source.is_absolute():
        source = root / source
    return source.resolve()


def expose(root: pathlib.Path, src_path: pathlib.Path | None = None) -> typing.ContextManager[None]:
    """Expose an Uptimely project's Python modules within a context.

    The project root and ``spec`` directory can be imported. The source
    directory defaults to ``src`` under the project root. It can be changed to
    an absolute path or a path relative to the project root.

    Args:
        root: Uptimely project root.
        src_path: Explicit Python source directory, or ``None`` for ``src``.

    Returns:
        A context manager that makes the project's Python modules available
        while keeping existing imports safe.

    Raises:
        NotADirectoryError: An explicit source directory does not exist.
    """
    root = root.resolve()
    source = resolve_src_path(root, src_path)
    if src_path is not None and not source.is_dir():
        raise NotADirectoryError(f"Project source path is not a directory: {source}")

    return imports.PythonModuleImportManager(
        root,
        source,
        module_roots=(root / paths.SPEC_SOURCE_DIR,),
        reserved_modules=("uptimely",),
    ).expose()
