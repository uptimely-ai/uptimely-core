"""Standard paths and conventions for an Uptimely analytics project."""

import dataclasses
import json
import pathlib
import shlex
import typing

import pydantic

from uptimely.compiler.plan import models as plan_models

CONFIG_DIR: typing.Final = pathlib.Path("config")
SPEC_SOURCE_DIR: typing.Final = CONFIG_DIR / "spec"
SPEC_PYTHON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.py"
DEFAULT_SPEC_ATTRIBUTE: typing.Final = "python_spec"
SPEC_JSON_ENTRY_FILE: typing.Final = SPEC_SOURCE_DIR / "spec.json"
COMPILER_CONFIG_FILE: typing.Final = CONFIG_DIR / "compiler.json"
ENGINE_CONFIG_FILE: typing.Final = CONFIG_DIR / "engine.json"

DATA_DIR: typing.Final = pathlib.Path("data")
FUNCTIONS_DIR: typing.Final = pathlib.Path("functions")

GENERATED_DIR: typing.Final = pathlib.Path("_generated")

SPEC_OUTPUT_DIR: typing.Final = GENERATED_DIR / "spec"
SPEC_JSON_FILE: typing.Final = SPEC_OUTPUT_DIR / "spec.json"

COMPILE_OUTPUT_DIR: typing.Final = GENERATED_DIR / "compile"
EXECUTION_PLAN_FILE: typing.Final = COMPILE_OUTPUT_DIR / "execution_plan.json"

EXPLORER_OUTPUT_DIR: typing.Final = GENERATED_DIR / "explorer"
EXPLORER_INDEX_FILE: typing.Final = EXPLORER_OUTPUT_DIR / "index.html"

BUILD_OUTPUT_DIR: typing.Final = GENERATED_DIR / "build"
BUILD_MANIFEST_FILE: typing.Final = BUILD_OUTPUT_DIR / "build.json"
BUILD_SPEC_FILE: typing.Final = BUILD_OUTPUT_DIR / "spec.json"
BUILD_EXECUTION_PLAN_FILE: typing.Final = BUILD_OUTPUT_DIR / "execution_plan.json"
BUILD_EXPLORER_DIR: typing.Final = BUILD_OUTPUT_DIR / "explorer"
BUILD_SCHEMA_VERSION: typing.Final = 1


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


class BuildArtifactPaths(pydantic.BaseModel):
    """Relative locations of the required artifacts in an active build."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    spec: str
    execution_plan: str
    explorer: str

    @pydantic.field_validator("spec", "execution_plan", "explorer")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Reject paths that are not safe to resolve under the bundle root."""
        return _validate_relative_path(value)

    @pydantic.model_validator(mode="after")
    def validate_distinct_paths(self) -> typing.Self:
        """Prevent required artifacts from colliding or containing one another."""
        paths = {
            "spec": pathlib.PurePosixPath(self.spec),
            "execution_plan": pathlib.PurePosixPath(self.execution_plan),
            "explorer": pathlib.PurePosixPath(self.explorer),
        }
        names = list(paths)
        for index, name in enumerate(names):
            for other_name in names[index + 1 :]:
                path, other = paths[name], paths[other_name]
                if path == other or path in other.parents or other in path.parents:
                    raise ValueError(f"Build artifact paths {name!r} and {other_name!r} overlap")
        return self


class BuildManifest(pydantic.BaseModel):
    """Versioned manifest describing one complete active build bundle."""

    model_config = pydantic.ConfigDict(extra="forbid", frozen=True, strict=True)

    schema_version: int
    uptimely_version: str
    features: list[str] | None
    artifacts: BuildArtifactPaths
    explorer_files: list[str]

    @pydantic.field_validator("schema_version")
    @classmethod
    def validate_schema_version(cls, value: int) -> int:
        """Reject bundle schemas this runtime does not support."""
        if value != BUILD_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported build schema version: {value}. "
                f"Supported version is {BUILD_SCHEMA_VERSION}."
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
        if value is None:
            return None
        if not isinstance(value, list) or not value:
            raise ValueError("features must be null or a nonempty list of feature names")
        if any(not isinstance(feature, str) or not feature.strip() for feature in value):
            raise ValueError("features must contain only nonempty feature names")
        return sorted(set(value))

    @pydantic.field_validator("explorer_files")
    @classmethod
    def validate_explorer_files(cls, values: list[str]) -> list[str]:
        """Require a unique inventory of safe paths that includes the entry page."""
        if not values:
            raise ValueError("explorer_files must contain the complete website file inventory")
        for value in values:
            _validate_relative_path(value)
        if len(set(values)) != len(values):
            raise ValueError("explorer_files must not contain duplicate paths")
        if "index.html" not in values:
            raise ValueError("explorer_files must include index.html")
        return values


class BuildError(RuntimeError):
    """An actionable failure while locating or validating an active build."""

    def __init__(
        self,
        status: typing.Literal["missing", "incomplete", "invalid"],
        detail: str,
        project_root: pathlib.Path,
    ) -> None:
        """Create a consistently formatted error with a safely quoted recovery command."""
        self.status = status
        self.detail = detail
        self.recovery_command = shlex.join(
            [
                "uptimely",
                "project",
                "build",
                "--project-root",
                str(project_root),
            ]
        )
        descriptions = {
            "missing": "No active build found",
            "incomplete": f"Active build is incomplete: {detail}",
            "invalid": f"Active build is invalid: {detail}",
        }
        action = "Create one" if status == "missing" else "Rebuild it"
        super().__init__(f"{descriptions[status]}. {action} with: {self.recovery_command}")


@dataclasses.dataclass(frozen=True)
class BuildBundle:
    """Validated locations and execution plan for one active build."""

    root: pathlib.Path
    manifest: BuildManifest
    spec_path: pathlib.Path
    execution_plan_path: pathlib.Path
    explorer_path: pathlib.Path
    execution_plan: plan_models.ExecutionPlan


def _resolve_bundle_path(
    bundle_root: pathlib.Path, relative_path: str, *, containment_root: pathlib.Path | None = None
) -> pathlib.Path:
    """Resolve a declared path and reject resolutions outside its root."""
    path = (bundle_root / pathlib.PurePosixPath(relative_path)).resolve()
    allowed_root = (containment_root or bundle_root).resolve()
    if not path.is_relative_to(allowed_root):
        raise ValueError(f"Artifact path escapes its bundle: {relative_path!r}")
    return path


def load_build_bundle(project_root: str | pathlib.Path) -> BuildBundle:
    """Load and validate the active build without compiling or regenerating artifacts.

    Args:
        project_root: Root directory of the analytics project.

    Returns:
        A validated bundle containing the saved execution plan and artifact paths.

    Raises:
        BuildError: If the bundle is missing, incomplete, or invalid.
    """
    project_root = pathlib.Path(project_root).resolve()
    bundle_root = project_root / BUILD_OUTPUT_DIR
    manifest_path = bundle_root / BUILD_MANIFEST_FILE.name
    if not bundle_root.exists():
        raise BuildError("missing", "", project_root)
    if not bundle_root.is_dir():
        raise BuildError("invalid", f"{BUILD_OUTPUT_DIR} is not a directory", project_root)
    if not manifest_path.is_file():
        raise BuildError("incomplete", f"missing {BUILD_MANIFEST_FILE.name}", project_root)

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = BuildManifest.model_validate(manifest_data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, pydantic.ValidationError) as error:
        raise BuildError("invalid", f"cannot read build manifest: {error}", project_root) from error

    try:
        spec_path = _resolve_bundle_path(bundle_root, manifest.artifacts.spec)
        execution_plan_path = _resolve_bundle_path(bundle_root, manifest.artifacts.execution_plan)
        explorer_path = _resolve_bundle_path(bundle_root, manifest.artifacts.explorer)
    except ValueError as error:
        raise BuildError("invalid", str(error), project_root) from error

    for artifact_path in (spec_path, execution_plan_path):
        if not artifact_path.is_file():
            relative_path = artifact_path.relative_to(bundle_root.resolve())
            raise BuildError("incomplete", f"missing artifact {relative_path}", project_root)
    if not explorer_path.is_dir():
        raise BuildError(
            "incomplete",
            f"missing website directory {manifest.artifacts.explorer}",
            project_root,
        )

    try:
        website_files: set[str] = set()
        for path in explorer_path.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"Website contains a symlink: {path.relative_to(explorer_path)}")
            if path.is_file():
                website_files.add(path.relative_to(explorer_path).as_posix())
        declared_files = set(manifest.explorer_files)
        missing_files = sorted(declared_files - website_files)
        undeclared_files = sorted(website_files - declared_files)
        if missing_files or undeclared_files:
            missing = ", ".join(missing_files) if missing_files else "none"
            undeclared = ", ".join(undeclared_files) if undeclared_files else "none"
            raise FileNotFoundError(
                f"website inventory mismatch (missing: {missing}; undeclared: {undeclared})"
            )
        for relative_path in manifest.explorer_files:
            _resolve_bundle_path(
                explorer_path,
                relative_path,
                containment_root=explorer_path,
            )
    except (OSError, ValueError) as error:
        raise BuildError("incomplete", str(error), project_root) from error

    try:
        execution_plan = plan_models.ExecutionPlan.from_json(execution_plan_path)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as error:
        raise BuildError("invalid", f"cannot load execution plan: {error}", project_root) from error

    return BuildBundle(
        root=bundle_root,
        manifest=manifest,
        spec_path=spec_path,
        execution_plan_path=execution_plan_path,
        explorer_path=explorer_path,
        execution_plan=execution_plan,
    )
