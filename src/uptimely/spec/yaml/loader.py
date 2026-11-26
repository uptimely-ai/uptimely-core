"""Load and compose YAML files into a Spec document."""

from __future__ import annotations

import math
import pathlib
import typing

from ruamel import yaml

from uptimely.spec import model, validation

from . import authoring

_YAML_SUFFIXES = {".yaml", ".yml"}
_INDEX_NAME = "index"


class _Composer:
    """Merge YAML contributions while retaining the origin of each value."""

    def __init__(self) -> None:
        self.document: dict[str, typing.Any] = {}
        self.origins: dict[tuple[str, ...], pathlib.Path] = {}

    def merge(
        self,
        target: dict[str, typing.Any],
        contribution: dict[str, typing.Any],
        source: pathlib.Path,
        path: tuple[str, ...] = (),
    ) -> None:
        for key, value in contribution.items():
            location = (*path, key)
            if key not in target:
                target[key] = value
                self._record(value, source, location)
            elif isinstance(target[key], dict) and isinstance(value, dict):
                self.merge(target[key], value, source, location)
            elif not self._equal(target[key], value):
                original = self.origins[location]
                raise ValueError(
                    f"Conflicting YAML values at {'.'.join(location)} in {original} and {source}"
                )

    def _record(self, value: typing.Any, source: pathlib.Path, path: tuple[str, ...]) -> None:
        self.origins[path] = source
        if isinstance(value, dict):
            for key, item in value.items():
                self._record(item, source, (*path, key))

    @classmethod
    def _equal(cls, left: typing.Any, right: typing.Any) -> bool:
        if type(left) is not type(right):
            return False
        if isinstance(left, list):
            return len(left) == len(right) and all(
                cls._equal(a, b) for a, b in zip(left, right, strict=True)
            )
        if isinstance(left, dict):
            return left.keys() == right.keys() and all(
                cls._equal(left[key], right[key]) for key in left
            )
        return left == right


def _json_value(value: object, source: pathlib.Path, ancestors: set[int]) -> typing.Any:
    """Copy YAML values into the JSON-compatible data model."""
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if math.isfinite(value):
            return value
        raise ValueError(f"{source}: YAML numbers must be finite")
    if isinstance(value, (dict, list)):
        if id(value) in ancestors:
            raise ValueError(f"{source}: recursive YAML aliases are not supported")
        ancestors.add(id(value))
        try:
            if isinstance(value, list):
                return [_json_value(item, source, ancestors) for item in value]
            result: dict[str, typing.Any] = {}
            for key, item in value.items():
                if not isinstance(key, str):
                    raise ValueError(f"{source}: YAML mapping keys must be strings")
                result[key] = _json_value(item, source, ancestors)
            return result
        finally:
            ancestors.remove(id(value))
    raise ValueError(f"{source}: unsupported YAML value type {type(value).__name__}")


def _read(path: pathlib.Path) -> typing.Any:
    parser = yaml.YAML(typ="safe")
    parser.allow_duplicate_keys = False
    try:
        with path.open(encoding="utf-8") as file:
            value = parser.load(file)
    except yaml.YAMLError as error:
        raise ValueError(f"Invalid YAML in {path}: {error}") from error
    return _json_value(value, path, set())


def load_document(path: str | pathlib.Path) -> dict[str, typing.Any]:
    """Read one YAML document or compose a directory of YAML fragments.

    Directory names and file stems become object keys. An ``index.yaml`` or
    ``index.yml`` contains fields at its directory's level.

    Args:
        path: YAML file or directory of YAML fragments.

    Returns:
        A JSON-compatible Spec document.

    Raises:
        OSError: A source cannot be read.
        ValueError: A source is invalid or contributions conflict.
    """
    root = pathlib.Path(path)
    if not root.is_dir():
        document = _read(root)
        if not isinstance(document, dict):
            raise ValueError(f"{root}: the Spec must be a YAML mapping")
        return document

    files = sorted(
        (item for item in root.rglob("*") if item.is_file() and item.suffix in _YAML_SUFFIXES),
        key=lambda item: (item.stem != _INDEX_NAME, item.relative_to(root).as_posix()),
    )
    if not files:
        raise ValueError(f"No YAML files found in {root}")
    composer = _Composer()
    for file in files:
        relative = file.relative_to(root)
        keys = list(relative.parts[:-1])
        value = _read(file)
        if file.stem == _INDEX_NAME:
            if not isinstance(value, dict):
                raise ValueError(f"{file}: an index must contain a YAML mapping")
        else:
            keys.append(file.stem)
        for key in reversed(keys):
            value = {key: value}
        composer.merge(composer.document, value, file)
    return composer.document


def load_spec(
    path: str | pathlib.Path, *, validate: bool = True, log_structure: bool = True
) -> model.Spec:
    """Load YAML into the shared Spec model and optionally validate semantics.

    Args:
        path: YAML file or directory of fragments.
        validate: Run Spec semantic validation after structural parsing.
        log_structure: Emit structural validation debug messages.

    Returns:
        The parsed Spec document.

    Raises:
        OSError: A source cannot be read.
        ValueError: A source or Spec declaration is invalid.
    """
    document = model.Spec.model_validate(
        authoring.to_document(load_document(path)), context={"log_structure": log_structure}
    )
    if validate:
        validation.validate_spec(document)
    return document
