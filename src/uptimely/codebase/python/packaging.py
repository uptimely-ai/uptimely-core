"""Stage Python implementation artifacts without installing dependencies."""

import pathlib
import shutil
import tomllib

from uptimely.codebase import packaging
from uptimely.project import paths

from . import REQUIREMENTS_FILE

PACKAGE_ID = "project"
SOURCE_DIR = f"{packaging.PACKAGES_DIR}/{PACKAGE_ID}"
RUNTIME_ID = "python"
_PROJECT_METADATA_FILE = "pyproject.toml"


class PythonPackager:
    """Package project Python source and optional requirements."""

    def stage(
        self,
        project_root: pathlib.Path,
        source: pathlib.Path,
        staging_root: pathlib.Path,
        runtimes_root: pathlib.Path,
    ) -> packaging.StagedCode:
        """Stage Python source and requirements, returning their paths and kinds."""
        artifacts = packaging.StagedCode()
        runtime_path = f"{packaging.RUNTIMES_DIR}/{RUNTIME_ID}/{REQUIREMENTS_FILE}"
        if self._stage_requirements(project_root, runtimes_root, staging_root / runtime_path):
            artifacts.runtimes[RUNTIME_ID] = runtime_path
        if source.is_dir():
            self._copy_source(source, staging_root / SOURCE_DIR)
            artifacts.packages[PACKAGE_ID] = packaging.CodePackage(
                path=SOURCE_DIR, runtime=RUNTIME_ID if RUNTIME_ID in artifacts.runtimes else None
            )
        return artifacts

    @staticmethod
    def _stage_requirements(
        project_root: pathlib.Path, runtimes_root: pathlib.Path, target: pathlib.Path
    ) -> bool:
        """Use explicit requirements or export static project dependencies."""
        for root in (runtimes_root / RUNTIME_ID, runtimes_root, project_root):
            requirements = root / REQUIREMENTS_FILE
            if requirements.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(requirements, target)
                return True

        metadata = project_root / _PROJECT_METADATA_FILE
        if not metadata.is_file():
            return False
        with metadata.open("rb") as stream:
            project = tomllib.load(stream).get("project", {})
        if not isinstance(project, dict):
            raise ValueError(f"{_PROJECT_METADATA_FILE}: expected a [project] table")
        if "dependencies" not in project:
            return False
        dependencies = project["dependencies"]
        if not isinstance(dependencies, list) or not all(
            isinstance(dependency, str)
            and dependency.strip()
            and not dependency.lstrip().startswith(("-", "#"))
            and dependency.splitlines() == [dependency]
            and not dependency.rstrip().endswith("\\")
            for dependency in dependencies
        ):
            raise ValueError(
                f"{_PROJECT_METADATA_FILE}: [project].dependencies must be an array "
                "of single-line requirement strings"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "".join(f"{dependency}\n" for dependency in dependencies),
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
