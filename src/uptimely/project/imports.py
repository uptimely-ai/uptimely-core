"""Configure Python import paths for an analytics project."""

import pathlib
import sys


def project_import_root(project_root: pathlib.Path) -> pathlib.Path:
    """Find the import root above a project's enclosing regular packages."""
    root = project_root.resolve()
    while (root / "__init__.py").is_file():
        root = root.parent
    return root


def prepare_project_root(project_root: pathlib.Path) -> None:
    """Make project modules importable without changing the working directory."""
    for path in (project_import_root(project_root), project_root.resolve()):
        root = str(path)
        if root not in sys.path:
            sys.path.insert(0, root)
