"""Check declared Python runtime requirements without importing project code."""

import importlib.metadata
import pathlib
import platform

from packaging import requirements, specifiers

from . import packaging as python_packaging


def check_compatibility(path: pathlib.Path) -> None:
    """Check declared requirements against the current Python environment.

    Read ``[project].requires-python`` and ``[project].dependencies`` from the
    bundled runtime definition. Compare the Python constraint with the running
    interpreter and evaluate dependency markers in its environment. For each
    applicable dependency, check that its distribution is installed and that
    its version satisfies the declared constraint, if any.

    The check reads installed distribution metadata without importing project
    code or installing packages. It does not check transitive dependencies,
    extras, or whether a distribution came from a declared direct URL.

    Args:
        path: Path to the bundled Python runtime TOML file. An existing file
            with neither runtime field requires no checks.

    Raises:
        ValueError: The definition is missing, unreadable, or invalid, or the
            environment does not meet its requirements. Interpreter mismatches,
            missing distributions, and incompatible versions are reported together.
    """
    try:
        definition = python_packaging.PythonRuntimeDefinition.from_project_file(path)
        if definition is None:
            if not path.is_file():
                raise FileNotFoundError(path)
            return
        python = platform.python_version()
        issues: list[str] = []
        if definition.requires_python and not specifiers.SpecifierSet(
            definition.requires_python
        ).contains(python, prereleases=True):
            issues.append(f"Python {python} does not satisfy {definition.requires_python}")
        for declared in definition.dependencies or ():
            requirement = requirements.Requirement(declared)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            try:
                installed = importlib.metadata.version(requirement.name)
            except importlib.metadata.PackageNotFoundError:
                issues.append(f"Missing dependency: {requirement}")
                continue
            if requirement.specifier and not requirement.specifier.contains(installed):
                issues.append(f"{requirement.name} {installed} does not satisfy {requirement}")
    except (OSError, ValueError) as error:
        raise ValueError(f"Invalid Python runtime definition at {path}: {error}") from error

    if issues:
        details = "\n".join(f"- {issue}" for issue in issues)
        raise ValueError(
            f"Python runtime preflight failed for {path}:\n{details}\n"
            "Use a compatible Python interpreter and install the required dependencies."
        )
