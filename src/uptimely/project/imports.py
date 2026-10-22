"""Prepare Python imports for an analytics project."""

import pathlib
import sys


def project_import_root(project_root: pathlib.Path) -> pathlib.Path:
    """Find the import root above a project's enclosing regular packages."""
    root = project_root.resolve()
    while (root / "__init__.py").is_file():
        root = root.parent
    return root


def prepare_imports(project_root: pathlib.Path) -> None:
    """Add project modules to Python's import path without changing the working directory."""
    roots = dict.fromkeys((project_root.resolve(), project_import_root(project_root)))
    for path in reversed(tuple(roots)):
        root = str(path)
        if root not in sys.path:
            sys.path.insert(0, root)
