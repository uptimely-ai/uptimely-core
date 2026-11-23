"""Data models describing a complete active build bundle."""

from __future__ import annotations

import dataclasses
import itertools
import pathlib
import typing

import pydantic

from uptimely.build import features
from uptimely.codebase import packaging
from uptimely.plan import models as plan_models
from uptimely.spec import model as spec_models

BUILD_VERSION = 6


class BuildArtifactPaths(pydantic.BaseModel):
    """Relative locations of artifacts in an active build."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    spec: str
    execution_plan: str
    explorer: typing.Literal["explorer.json"] | None = None
    code: packaging.CodeArtifacts

    @pydantic.field_validator("spec", "execution_plan")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Reject paths that are not safe to resolve under the bundle root."""
        return cls._validate_relative_path(value)

    @staticmethod
    def _validate_relative_path(value: str) -> str:
        """Require a canonical POSIX path that cannot escape the build directory."""
        if not value or "\\" in value:
            raise ValueError("Build artifact paths must be nonempty relative POSIX paths")
        path = pathlib.PurePosixPath(value)
        if (
            path.is_absolute()
            or pathlib.PureWindowsPath(value).drive
            or not path.parts
            or any(part in {".", ".."} for part in path.parts)
            or path.as_posix() != value
        ):
            raise ValueError(f"Build artifact path must stay within the build directory: {value!r}")
        return value

    @pydantic.model_validator(mode="after")
    def validate_distinct_paths(self) -> typing.Self:
        """Prevent required artifacts from colliding or containing one another."""
        artifact_paths = self._declared_artifact_paths()
        for (name, artifact_path), (other_name, other_path) in itertools.combinations(
            artifact_paths.items(), 2
        ):
            if (
                artifact_path == other_path
                or artifact_path in other_path.parents
                or other_path in artifact_path.parents
            ):
                raise ValueError(f"Build artifact paths {name!r} and {other_name!r} overlap")
        return self

    def _declared_artifact_paths(self) -> dict[str, pathlib.PurePosixPath]:
        """Return all declared artifact paths as normalized POSIX paths."""
        artifact_paths = {
            "manifest": pathlib.PurePosixPath("build.json"),
            "spec": pathlib.PurePosixPath(self.spec),
            "execution_plan": pathlib.PurePosixPath(self.execution_plan),
        }
        if self.code.src is not None:
            src = pathlib.PurePosixPath(self._validate_relative_path(self.code.src))
            if len(src.parts) != 2 or src.parts[0] != packaging.PACKAGES_DIR:
                raise ValueError("Code source must be a directory under packages/")
            artifact_paths["code.src"] = src
        if self.code.requirements is not None:
            requirements_file = pathlib.PurePosixPath(
                self._validate_relative_path(self.code.requirements)
            )
            if (
                len(requirements_file.parts) < 2
                or requirements_file.parts[0] != packaging.RUNTIME_DIR
            ):
                raise ValueError("Runtime definition must be under runtime/")
            artifact_paths["code.requirements"] = requirements_file
        if self.explorer is not None:
            artifact_paths["explorer"] = pathlib.PurePosixPath(self.explorer)
        return artifact_paths


class BuildManifest(pydantic.BaseModel):
    """Versioned manifest describing one complete active build bundle."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    build_version: int
    uptimely_version: str
    features: list[str] | None
    artifacts: BuildArtifactPaths
    spec_source: str | None = pydantic.Field(default=None, min_length=1)

    @pydantic.field_validator("build_version")
    @classmethod
    def validate_build_version(cls, value: int) -> int:
        """Reject build formats this runtime does not support."""
        if value != BUILD_VERSION:
            raise ValueError(
                f"Unsupported build version: {value}. Supported version is {BUILD_VERSION}."
            )
        return value

    @pydantic.field_validator("uptimely_version")
    @classmethod
    def validate_uptimely_version(cls, value: str) -> str:
        """Require the producer's Uptimely version."""
        if not value.strip():
            raise ValueError("uptimely_version must be nonempty")
        return value

    @pydantic.field_validator("features", mode="before")
    @classmethod
    def normalize_features(cls, value: object) -> object:
        """Represent all features as null and normalize explicit selections."""
        if value is not None and not isinstance(value, list):
            raise ValueError("features must be null or a nonempty list of feature names")
        return features.normalize_features(value)


@dataclasses.dataclass(frozen=True)
class BuildBundle:
    """Validated artifacts, execution plan, and portable code for one active build."""

    project_root: pathlib.Path
    root: pathlib.Path
    manifest: BuildManifest
    spec_path: pathlib.Path
    spec_definition: spec_models.Spec
    execution_plan_path: pathlib.Path
    execution_plan: plan_models.ExecutionPlan
    source_path: pathlib.Path | None = None
    requirements_file: pathlib.Path | None = None
    explorer_path: pathlib.Path | None = None
