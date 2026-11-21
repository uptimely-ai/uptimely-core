"""Stage Python implementation artifacts without installing dependencies."""

from __future__ import annotations

import dataclasses
import json
import pathlib
import shutil
import tomllib

from uptimely.codebase import packaging
from uptimely.project import paths

PACKAGE_ID = "project"
SOURCE_DIR = f"{packaging.PACKAGES_DIR}/{PACKAGE_ID}"
RUNTIME_TYPE = "python"
_PROJECT_METADATA_FILE = "pyproject.toml"


@dataclasses.dataclass(frozen=True)
class PythonRuntimeDefinition:
    """Static Python runtime fields exported from project metadata."""

    requires_python: str | None = None
    dependencies: tuple[str, ...] | None = None

    @classmethod
    def from_project_file(cls, metadata_path: pathlib.Path) -> PythonRuntimeDefinition | None:
        """Read supported runtime fields from a project metadata file.

        Args:
            metadata_path: Path to the project's ``pyproject.toml``.

        Returns:
            A runtime definition, or ``None`` when the file does not declare any.

        Raises:
            ValueError: The TOML table or one of its runtime fields is invalid.
        """
        if not metadata_path.is_file():
            return None
        with metadata_path.open("rb") as stream:
            project = tomllib.load(stream).get("project", {})
        if not isinstance(project, dict):
            raise ValueError(f"{metadata_path}: expected a [project] table")

        requires_python = cls._read_requires_python(project, metadata_path)
        dependencies = cls._read_dependencies(project, metadata_path)
        if requires_python is None and dependencies is None:
            return None
        return cls(requires_python=requires_python, dependencies=dependencies)

    @staticmethod
    def _read_requires_python(
        project: dict[str, object], metadata_path: pathlib.Path
    ) -> str | None:
        """Return and validate the optional supported Python version range."""
        if "requires-python" not in project:
            return None
        value = project["requires-python"]
        if not isinstance(value, str) or not value.strip():
            raise ValueError(
                f"{metadata_path}: [project].requires-python must be a nonempty string"
            )
        return value

    @staticmethod
    def _read_dependencies(
        project: dict[str, object], metadata_path: pathlib.Path
    ) -> tuple[str, ...] | None:
        """Return and validate optional package requirement strings."""
        if "dependencies" not in project:
            return None
        dependencies = project["dependencies"]
        if not isinstance(dependencies, list) or not all(
            PythonRuntimeDefinition._is_valid_dependency(dependency) for dependency in dependencies
        ):
            raise ValueError(
                f"{metadata_path}: [project].dependencies must be an array "
                "of single-line requirement strings"
            )
        return tuple(dependencies)

    @staticmethod
    def _is_valid_dependency(value: object) -> bool:
        """Return whether a value is safe to serialize as one requirement."""
        return (
            isinstance(value, str)
            and bool(value.strip())
            and not value.lstrip().startswith(("-", "#"))
            and value.splitlines() == [value]
            and not value.rstrip().endswith("\\")
        )

    def to_toml(self) -> str:
        """Serialize the supported fields as a standalone project definition."""
        fields = ["[project]"]
        if self.requires_python is not None:
            fields.append(f"requires-python = {self._toml_string(self.requires_python)}")
        if self.dependencies is not None:
            dependencies = ", ".join(self._toml_string(item) for item in self.dependencies)
            fields.append(f"dependencies = [{dependencies}]")
        return "\n".join(fields) + "\n"

    @staticmethod
    def _toml_string(value: str) -> str:
        """Quote one string using TOML-compatible JSON escapes."""
        return json.dumps(value, ensure_ascii=False).replace("\x7f", r"\u007f")


class PythonPackager:
    """Package project Python source and optional runtime metadata."""

    def stage(
        self,
        project_root: pathlib.Path,
        source: pathlib.Path,
        staging_root: pathlib.Path,
        runtime_root: pathlib.Path,
    ) -> packaging.StagedCode:
        """Stage Python source and its runtime definition."""
        artifacts = packaging.StagedCode()
        runtime_path = self._stage_runtime(project_root, runtime_root, staging_root)
        artifacts.runtime = packaging.CodeRuntime(type=RUNTIME_TYPE, path=runtime_path)
        if source.is_dir():
            self._copy_source(source, staging_root / SOURCE_DIR)
            artifacts.packages[PACKAGE_ID] = packaging.CodePackage(path=SOURCE_DIR)
        return artifacts

    @staticmethod
    def _stage_runtime(
        project_root: pathlib.Path, runtime_root: pathlib.Path, staging_root: pathlib.Path
    ) -> str | None:
        """Stage an explicit runtime definition or export root metadata."""
        relative_path = pathlib.PurePosixPath(packaging.RUNTIME_DIR, _PROJECT_METADATA_FILE)
        target = staging_root.joinpath(*relative_path.parts)
        metadata_path = project_root / _PROJECT_METADATA_FILE
        if (
            runtime_root == project_root / packaging.RUNTIME_DIR
            and not (runtime_root / _PROJECT_METADATA_FILE).is_file()
        ):
            legacy_root = project_root / "runtimes"
            if any(
                (root / _PROJECT_METADATA_FILE).is_file()
                for root in (legacy_root, legacy_root / RUNTIME_TYPE)
            ):
                raise ValueError("Move the Python runtime definition from runtimes/ to runtime/")
        explicit_path = PythonPackager._find_explicit_runtime(metadata_path, runtime_root)
        if explicit_path is not None:
            contents = PythonPackager._read_valid_toml(explicit_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(contents)
            return relative_path.as_posix()

        definition = PythonRuntimeDefinition.from_project_file(metadata_path)
        if definition is None:
            return None
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(definition.to_toml(), encoding="utf-8", newline="\n")
        return relative_path.as_posix()

    @staticmethod
    def _find_explicit_runtime(
        project_metadata: pathlib.Path, runtime_root: pathlib.Path
    ) -> pathlib.Path | None:
        """Find a runtime definition outside root metadata."""
        candidate = runtime_root / _PROJECT_METADATA_FILE
        if candidate.is_file() and candidate.resolve() != project_metadata.resolve():
            return candidate
        return None

    @staticmethod
    def _read_valid_toml(path: pathlib.Path) -> bytes:
        """Read a TOML file while reporting invalid content with its path."""
        contents = path.read_bytes()
        try:
            tomllib.loads(contents.decode("utf-8"))
        except (UnicodeError, tomllib.TOMLDecodeError) as error:
            raise ValueError(f"{path}: {error}") from error
        return contents

    @staticmethod
    def _copy_source(source: pathlib.Path, target: pathlib.Path) -> None:
        """Copy source without symbolic links, build output, or bytecode."""
        if any(path.is_symlink() for path in source.rglob("*")):
            raise ValueError("Python source artifact cannot contain symbolic links")

        def ignore(directory: str, names: list[str]) -> list[str]:
            return [
                name
                for name in names
                if name == "__pycache__"
                or name.endswith((".pyc", ".pyo"))
                or (
                    pathlib.Path(directory) == source and name in {".git", paths.ARTIFACTS_DIR.name}
                )
            ]

        shutil.copytree(source, target, ignore=ignore)
