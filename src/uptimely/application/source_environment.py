"""Isolation of project-local Python imports during builds and runs."""

from __future__ import annotations

import contextlib
import pathlib
import sys
import threading
import typing

from uptimely.codebase.python import entrypoint

from . import defaults


class ProjectSourceEnvironment:
    """Activate a project's Python source paths without leaking import state."""

    _LOCK = threading.RLock()
    _ACTIVE_ROOTS: list[tuple[pathlib.Path, pathlib.Path]] = []
    _RESERVED_MODULES = frozenset({"uptimely"})

    def __init__(self, root: pathlib.Path, src_path: pathlib.Path | None = None) -> None:
        self.root = root
        self.src_path = src_path

    @contextlib.contextmanager
    def activate(self) -> typing.Iterator[None]:
        """Make project modules importable while the environment is active."""
        root = self.root.resolve()
        source = root / defaults.DEFAULT_SRC_PATH if self.src_path is None else self.src_path
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if self.src_path is not None and not source.is_dir():
            raise NotADirectoryError(f"Project source path is not a directory: {source}")

        directories = [root]
        import_root = entrypoint.Module.find_import_root(root)
        if import_root != root:
            directories.append(import_root)
        if source.is_dir():
            directories.insert(0, source)

        active_root = (root, source)
        names = {"spec"} if (root / "spec").is_dir() else set()
        if import_root != root:
            names.add(root.relative_to(import_root).parts[0])
        if source.is_dir():
            names.update(
                item.stem if item.is_file() else item.name
                for item in source.iterdir()
                if (
                    (item.is_file() and item.suffix == ".py" and item.stem.isidentifier())
                    or (item.is_dir() and item.name.isidentifier())
                )
                and not item.name.startswith("_")
                and item.stem not in sys.stdlib_module_names
                and item.stem not in self._RESERVED_MODULES
            )

        with self._LOCK:
            if self._ACTIVE_ROOTS and self._ACTIVE_ROOTS[-1] == active_root:
                yield
                return
            original_path = sys.path[:]
            previous = {
                name: module
                for name, module in sys.modules.copy().items()
                if name.partition(".")[0] in names
            }
            for name in previous:
                del sys.modules[name]
            sys.path[:0] = [str(directory) for directory in directories]
            self._ACTIVE_ROOTS.append(active_root)
            try:
                yield
            finally:
                self._ACTIVE_ROOTS.pop()
                for name in tuple(sys.modules):
                    if name.partition(".")[0] in names:
                        del sys.modules[name]
                sys.modules.update(previous)
                sys.path[:] = original_path


def project_source_path(
    root: pathlib.Path, src_path: pathlib.Path | None = None
) -> typing.ContextManager[None]:
    """Make project modules importable for the duration of an operation."""
    return ProjectSourceEnvironment(root, src_path).activate()
