"""Stage Python implementation artifacts without installing dependencies."""

import json
import pathlib
import shutil
import tomllib

from uptimely.codebase import packaging
from uptimely.project import paths

PACKAGE_ID = "project"
SOURCE_DIR = f"{packaging.PACKAGES_DIR}/{PACKAGE_ID}"
RUNTIME_ID = "python"
_PROJECT_METADATA_FILE = "pyproject.toml"


class PythonPackager:
    """Package project Python source and optional runtime metadata."""

    def stage(
        self,
        project_root: pathlib.Path,
        source: pathlib.Path,
        staging_root: pathlib.Path,
        runtimes_root: pathlib.Path,
    ) -> packaging.StagedCode:
        """Stage Python source and its runtime definition."""
        artifacts = packaging.StagedCode()
        runtime_path = f"{packaging.RUNTIMES_DIR}/{RUNTIME_ID}/{_PROJECT_METADATA_FILE}"
        if self._stage_runtime(project_root, runtimes_root, staging_root / runtime_path):
            artifacts.runtimes[RUNTIME_ID] = runtime_path
        if source.is_dir():
            self._copy_source(source, staging_root / SOURCE_DIR)
            artifacts.packages[PACKAGE_ID] = packaging.CodePackage(
                path=SOURCE_DIR, runtime=RUNTIME_ID if RUNTIME_ID in artifacts.runtimes else None
            )
        return artifacts

    @staticmethod
    def _stage_runtime(
        project_root: pathlib.Path, runtimes_root: pathlib.Path, target: pathlib.Path
    ) -> bool:
        """Copy an explicit definition or export the root's static runtime fields."""
        metadata = project_root / _PROJECT_METADATA_FILE
        for root in (runtimes_root / RUNTIME_ID, runtimes_root):
            definition = root / _PROJECT_METADATA_FILE
            if definition.is_file() and definition.resolve() != metadata.resolve():
                contents = definition.read_bytes()
                try:
                    tomllib.loads(contents.decode("utf-8"))
                except ValueError as error:
                    raise ValueError(f"{definition}: {error}") from error
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(contents)
                return True

        if not metadata.is_file():
            return False
        with metadata.open("rb") as stream:
            project = tomllib.load(stream).get("project", {})
        if not isinstance(project, dict):
            raise ValueError(f"{metadata}: expected a [project] table")
        runtime = {
            key: project[key] for key in ("requires-python", "dependencies") if key in project
        }
        if not runtime:
            return False
        if "requires-python" in runtime and (
            not isinstance(runtime["requires-python"], str)
            or not runtime["requires-python"].strip()
        ):
            raise ValueError(f"{metadata}: [project].requires-python must be a nonempty string")
        dependencies = runtime.get("dependencies", [])
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str)
            and dependency.strip()
            and not dependency.lstrip().startswith(("-", "#"))
            and dependency.splitlines() == [dependency]
            and not dependency.rstrip().endswith("\\")
            for dependency in dependencies
        ):
            raise ValueError(
                f"{metadata}: [project].dependencies must be an array "
                "of single-line requirement strings"
            )
        # JSON strings and string arrays use TOML-compatible escapes, except for raw DEL.
        fields = "".join(
            f"{key} = " + json.dumps(value, ensure_ascii=False).replace("\x7f", r"\u007f") + "\n"
            for key, value in runtime.items()
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            f"[project]\n{fields}",
            encoding="utf-8",
            newline="\n",
        )
        return True

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
