"""Isolate activation of project-local Python imports."""

from __future__ import annotations

import collections.abc
import contextlib
import pathlib
import sys
import threading
import typing

from . import entrypoint


class PythonSourceEnvironment:
    """Activate Python source directories without leaking import state."""

    _LOCK = threading.RLock()
    _ACTIVE_ROOTS: list[tuple[pathlib.Path, pathlib.Path]] = []

    def __init__(
        self,
        root: pathlib.Path,
        source: pathlib.Path,
        *,
        module_roots: collections.abc.Iterable[pathlib.Path] = (),
        reserved_modules: collections.abc.Iterable[str] = (),
    ) -> None:
        self.root = root.resolve()
        self.source = source.resolve()
        self.module_roots = tuple(path.resolve() for path in module_roots)
        self.reserved_modules = frozenset(reserved_modules)

    @contextlib.contextmanager
    def activate(self) -> typing.Iterator[None]:
        """Make configured Python modules importable while the environment is active."""
        directories = [self.root]
        import_root = entrypoint.Module.find_import_root(self.root)
        if import_root != self.root:
            directories.append(import_root)
        if self.source.is_dir():
            directories.insert(0, self.source)

        active_root = (self.root, self.source)
        names = {
            module_root.name
            for module_root in self.module_roots
            if module_root.is_dir() and module_root.name.isidentifier()
        }
        if import_root != self.root:
            names.add(self.root.relative_to(import_root).parts[0])
        if self.source.is_dir():
            names.update(
                item.stem if item.is_file() else item.name
                for item in self.source.iterdir()
                if (
                    (item.is_file() and item.suffix == ".py" and item.stem.isidentifier())
                    or (item.is_dir() and item.name.isidentifier())
                )
                and not item.name.startswith("_")
                and item.stem not in sys.stdlib_module_names
                and item.stem not in self.reserved_modules
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
