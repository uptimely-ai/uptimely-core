"""Contract for staging implementation artifacts in a project build."""

import dataclasses
import pathlib
import typing

import pydantic

type ArtifactKind = typing.Literal["file", "directory"]

PACKAGES_DIR = "packages"
RUNTIMES_DIR = "runtimes"


class CodePackage(pydantic.BaseModel):
    """A bundled package directory and its optional runtime ID."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str
    runtime: str | None = None


@dataclasses.dataclass
class StagedCode:
    """Relative paths for packages and runtimes, with their assignments."""

    packages: dict[str, CodePackage] = dataclasses.field(default_factory=dict)
    runtimes: dict[str, str] = dataclasses.field(default_factory=dict)

    def validate_layout(self, staging_root: pathlib.Path) -> None:
        """Check that the bundle groups implementation and runtime files by ID."""
        for runtime, path in self.runtimes.items():
            parts = pathlib.PurePosixPath(path).parts
            if len(parts) < 3 or parts[:2] != (RUNTIMES_DIR, runtime):
                raise ValueError(
                    f"Runtime {runtime!r} must have its definition under runtimes/{runtime}/"
                )

        for directory, ids in (
            (PACKAGES_DIR, set(self.packages)),
            (RUNTIMES_DIR, set(self.runtimes)),
        ):
            root = staging_root / directory
            if not root.exists() and not root.is_symlink() and not ids:
                continue
            if root.is_symlink() or not root.is_dir():
                raise ValueError(f"Expected bundle directory {directory}/")
            entries = tuple(root.iterdir())
            if {entry.name for entry in entries} != ids or any(
                entry.is_symlink() or not entry.is_dir() for entry in entries
            ):
                raise ValueError(f"{directory}/ must contain only declared ID directories")


class CodePackager(typing.Protocol):
    """Supply implementation files without owning the build lifecycle."""

    def stage(
        self,
        project_root: pathlib.Path,
        source: pathlib.Path,
        staging_root: pathlib.Path,
        runtimes_root: pathlib.Path,
    ) -> StagedCode:
        """Stage implementation and runtime files and describe their relationship."""
        ...
