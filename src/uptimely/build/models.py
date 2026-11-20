"""Data models describing a complete active build bundle."""

from __future__ import annotations

import dataclasses
import pathlib
import typing

import pydantic

from uptimely.build import features
from uptimely.codebase import packaging
from uptimely.plan import models as plan_models
from uptimely.spec import model as spec_models

BUILD_VERSION = 2


class BuildArtifactPaths(pydantic.BaseModel):
    """Relative locations of artifacts in an active build."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    spec: str
    execution_plan: str
    packages: dict[str, packaging.CodePackage] = pydantic.Field(default_factory=dict)
    runtimes: dict[str, str] = pydantic.Field(default_factory=dict)

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
        artifact_paths = {
            "manifest": pathlib.PurePosixPath("build.json"),
            "spec": pathlib.PurePosixPath(self.spec),
            "execution_plan": pathlib.PurePosixPath(self.execution_plan),
            **{
                f"package:{package_id}": pathlib.PurePosixPath(
                    self._validate_relative_path(entry.path)
                )
                for package_id, entry in self.packages.items()
            },
            **{
                f"runtime:{runtime}": pathlib.PurePosixPath(self._validate_relative_path(path))
                for runtime, path in self.runtimes.items()
            },
        }
        names = list(artifact_paths)
        for index, name in enumerate(names):
            for other_name in names[index + 1 :]:
                artifact_path, other_path = artifact_paths[name], artifact_paths[other_name]
                if (
                    artifact_path == other_path
                    or artifact_path in other_path.parents
                    or other_path in artifact_path.parents
                ):
                    raise ValueError(f"Build artifact paths {name!r} and {other_name!r} overlap")
        return self

    @pydantic.model_validator(mode="after")
    def validate_code_packages(self) -> typing.Self:
        """Check package IDs against directory names and validate runtime references."""
        for package_id, entry in self.packages.items():
            if pathlib.PurePosixPath(entry.path).parts != (packaging.PACKAGES_DIR, package_id):
                raise ValueError(f"Code package {package_id!r} must match its directory name")
            if entry.runtime is not None and entry.runtime not in self.runtimes:
                raise ValueError(
                    f"Code package {package_id!r} refers to undeclared runtime {entry.runtime!r}"
                )
        return self


class BuildManifest(pydantic.BaseModel):
    """Versioned manifest describing one complete active build bundle."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    build_version: int
    uptimely_version: str
    features: list[str] | None
    artifacts: BuildArtifactPaths
    src_path: str | None = pydantic.Field(default=None, min_length=1)
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
    package_paths: dict[str, pathlib.Path] = dataclasses.field(default_factory=dict)
    runtime_paths: dict[str, pathlib.Path] = dataclasses.field(default_factory=dict)
