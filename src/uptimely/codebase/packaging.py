"""Contract for staging implementation artifacts in a project build."""

import dataclasses
import pathlib
import typing

import pydantic

type ArtifactKind = typing.Literal["file", "directory"]

PACKAGES_DIR = "packages"
RUNTIME_DIR = "runtime"


class CodePackage(pydantic.BaseModel):
    """A bundled package directory."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    path: str


class CodeRuntime(pydantic.BaseModel):
    """The project's runtime type and optional bundled definition file."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    type: str = pydantic.Field(min_length=1)
    path: str | None = None

    @pydantic.field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        """Require a nonblank runtime type."""
        if not value.strip():
            raise ValueError("Runtime type must be nonblank")
        return value


@dataclasses.dataclass
class StagedCode:
    """Relative paths for packages and the optional project runtime."""

    packages: dict[str, CodePackage] = dataclasses.field(default_factory=dict)
    runtime: CodeRuntime | None = None

    def validate_layout(self, staging_root: pathlib.Path) -> None:
        """Check that implementation files match their declared package IDs."""
        root = staging_root / PACKAGES_DIR
        if root.exists() or root.is_symlink() or self.packages:
            if root.is_symlink() or not root.is_dir():
                raise ValueError(f"Expected bundle directory {PACKAGES_DIR}/")
            entries = tuple(root.iterdir())
            if {entry.name for entry in entries} != set(self.packages) or any(
                entry.is_symlink() or not entry.is_dir() for entry in entries
            ):
                raise ValueError(f"{PACKAGES_DIR}/ must contain only declared ID directories")
        runtime_root = staging_root / RUNTIME_DIR
        if self.runtime is None or self.runtime.path is None:
            if runtime_root.exists() or runtime_root.is_symlink():
                raise ValueError("runtime/ must not exist without a declared runtime definition")
        elif runtime_root.is_symlink() or not runtime_root.is_dir():
            raise ValueError("Expected bundle directory runtime/")


class CodePackager(typing.Protocol):
    """Supply implementation files without owning the build lifecycle."""

    def stage(
        self,
        project_root: pathlib.Path,
        source: pathlib.Path,
        staging_root: pathlib.Path,
        runtime_root: pathlib.Path,
    ) -> StagedCode:
        """Stage implementation files and the project runtime definition."""
        ...
