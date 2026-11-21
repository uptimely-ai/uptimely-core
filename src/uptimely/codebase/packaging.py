"""Contract for staging implementation artifacts in a project build."""

import dataclasses
import pathlib
import typing

import pydantic

type ArtifactKind = typing.Literal["file", "directory"]

PACKAGES_DIR = "packages"
RUNTIME_DIR = "runtime"


class CodeArtifacts(pydantic.BaseModel):
    """The project's language and optional bundled code and requirements paths."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    language: str = pydantic.Field(min_length=1)
    requirements: str | None = None
    src: str | None = None

    @pydantic.field_validator("language")
    @classmethod
    def validate_language(cls, value: str) -> str:
        """Require a nonblank code language."""
        if not value.strip():
            raise ValueError("Code language must be nonblank")
        return value


@dataclasses.dataclass
class StagedCode:
    """Relative paths for project code and its optional requirements definition."""

    language: str | None = None
    requirements: str | None = None
    src: str | None = None

    def validate_layout(self, staging_root: pathlib.Path) -> None:
        """Check that staged directories match the declared code paths."""
        root = staging_root / PACKAGES_DIR
        if root.exists() or root.is_symlink() or self.src is not None:
            if root.is_symlink() or not root.is_dir():
                raise ValueError(f"Expected bundle directory {PACKAGES_DIR}/")
            entries = tuple(root.iterdir())
            expected = {pathlib.PurePosixPath(self.src).name} if self.src is not None else set()
            if {entry.name for entry in entries} != expected or any(
                entry.is_symlink() or not entry.is_dir() for entry in entries
            ):
                raise ValueError(f"{PACKAGES_DIR}/ must contain only the declared source directory")
        runtime_root = staging_root / RUNTIME_DIR
        if self.requirements is None:
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
        requirements_file: pathlib.Path | None,
    ) -> StagedCode:
        """Stage implementation files and the project runtime definition."""
        ...
