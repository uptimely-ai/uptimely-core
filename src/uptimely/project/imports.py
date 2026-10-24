"""Resolve the package import root for a Python spec source."""

import pathlib


def project_import_root(project_root: pathlib.Path) -> pathlib.Path:
    """Find the import root above a project's enclosing regular packages."""
    root = project_root.resolve()
    while (root / "__init__.py").is_file():
        root = root.parent
    return root
