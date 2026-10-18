"""Active build bundle manifest and validation."""

from __future__ import annotations

import contextlib
import dataclasses
import importlib
import importlib.metadata
import json
import os
import pathlib
import shlex
import shutil
import sys
import tempfile
import typing
import uuid

import jinja2
import pydantic

from uptimely import compiler, spec
from uptimely.compiler.plan import models as plan_models
from uptimely.spec import python as python_spec

if os.name == "nt":
    import msvcrt
else:
    import fcntl

from . import paths

SpecSource = str | pathlib.Path | None
FeatureSelection = typing.Collection[str] | None


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
        artifact_paths = {
            "spec": pathlib.PurePosixPath(self.spec),
            "execution_plan": pathlib.PurePosixPath(self.execution_plan),
            "explorer": pathlib.PurePosixPath(self.explorer),
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
        if value != paths.BUILD_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported build schema version: {value}. "
                f"Supported version is {paths.BUILD_SCHEMA_VERSION}."
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


class ProjectBuildError(RuntimeError):
    """A failure while building or publishing an active bundle."""

    def __init__(self, stage: str, detail: str) -> None:
        self.stage = stage
        self.detail = detail
        super().__init__(f"Project build {stage} failed: {detail}")


class BuildLockError(RuntimeError):
    """A build cannot acquire the active bundle lock."""


@dataclasses.dataclass(frozen=True)
class BuildBundle:
    """Validated locations and execution plan for one active build."""

    root: pathlib.Path
    manifest: BuildManifest
    spec_path: pathlib.Path
    execution_plan_path: pathlib.Path
    explorer_path: pathlib.Path
    execution_plan: plan_models.ExecutionPlan


@contextlib.contextmanager
def build_lock(
    project_root: str | pathlib.Path, *, exclusive: bool, wait: bool = True
) -> typing.Generator[None]:
    """Coordinate bundle reads and writes across builders and consumers.

    Builders should acquire a nonblocking exclusive lock. Consumers acquire a
    lock which may be held for the lifetime of a serving process. On platforms
    with shared file locks, multiple consumers can hold it concurrently.
    """
    project_root = pathlib.Path(project_root).resolve()
    lock_path = project_root / paths.GENERATED_DIR / ".build.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock_file:
        if os.name == "nt":
            lock_file.seek(0)
            if lock_file.read(1) == b"":
                lock_file.write(b"\0")
                lock_file.flush()
            lock_file.seek(0)
            mode = msvcrt.LK_LOCK if wait else msvcrt.LK_NBLCK
            try:
                msvcrt.locking(lock_file.fileno(), mode, 1)
            except OSError as error:
                raise BuildLockError(
                    f"Cannot acquire the active build lock at {lock_path}; another build or "
                    f"consumer may be using the bundle. Stop it or retry when it finishes: "
                    f"{error}"
                ) from error
        else:
            operation = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
            if not wait:
                operation |= fcntl.LOCK_NB
            try:
                fcntl.flock(lock_file.fileno(), operation)
            except OSError as error:
                raise BuildLockError(
                    f"Cannot acquire the active build lock at {lock_path}; another build or "
                    f"consumer may be using the bundle. Stop it or retry when it finishes: "
                    f"{error}"
                ) from error
        try:
            yield
        finally:
            if os.name == "nt":
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def project_import_root(project_root: pathlib.Path) -> pathlib.Path:
    """Find the import root above a project's enclosing regular packages."""
    root = project_root.resolve()
    while (root / "__init__.py").is_file():
        root = root.parent
    return root


def prepare_project_root(project_root: pathlib.Path) -> None:
    """Make project function entrypoints importable without changing directories."""
    for path in (project_import_root(project_root), project_root.resolve()):
        root = str(path)
        if root not in sys.path:
            sys.path.insert(0, root)


def load_spec_source(
    entrypoint: str | None,
    project_root: pathlib.Path,
    *,
    source: SpecSource = None,
) -> spec.Spec:
    """Load and validate an explicit or discovered Python or JSON spec source."""
    if entrypoint is not None and source is not None:
        raise ValueError("Specify either a Python entrypoint or a spec JSON source, not both")
    prepare_project_root(project_root)
    if entrypoint is None and source is None:
        python_source = project_root / paths.SPEC_PYTHON_ENTRY_FILE
        json_source = project_root / paths.SPEC_JSON_ENTRY_FILE
        if python_source.is_file() and json_source.is_file():
            raise ValueError(
                f"Ambiguous spec sources: {python_source} and {json_source}. "
                "Select one with --entrypoint or --spec."
            )
        if python_source.is_file():
            module = ".".join(
                python_source.resolve()
                .relative_to(project_import_root(project_root))
                .with_suffix("")
                .parts
            )
            entrypoint = f"{module}:{paths.DEFAULT_SPEC_ATTRIBUTE}"
        elif json_source.is_file():
            source = json_source
        else:
            raise FileNotFoundError(
                f"No spec source found. Expected {python_source} or {json_source}. "
                "Alternatively, specify --entrypoint or --spec."
            )
    if source is not None:
        return spec.load_spec(source)
    if entrypoint is None:
        raise ValueError("A spec Python entrypoint or JSON source is required")
    module, separator, attribute = entrypoint.partition(":")
    if (
        not separator
        or not all(part.isidentifier() for part in module.split("."))
        or not attribute.isidentifier()
    ):
        raise ValueError(f"Invalid spec entrypoint: {entrypoint!r}. Expected 'module:attribute'.")
    declaration = getattr(importlib.import_module(module), attribute)
    if not isinstance(declaration, python_spec.PythonSpec):
        raise TypeError(f"{entrypoint} must be a PythonSpec")
    return spec.from_python(
        entities=declaration.entities,
        dimensions=declaration.dimensions,
        name=declaration.name,
    )


def _resolve_bundle_path(
    bundle_root: pathlib.Path, relative_path: str, *, containment_root: pathlib.Path | None = None
) -> pathlib.Path:
    """Resolve a declared path and reject resolutions outside its root."""
    path = (bundle_root / pathlib.PurePosixPath(relative_path)).resolve()
    allowed_root = (containment_root or bundle_root).resolve()
    if not path.is_relative_to(allowed_root):
        raise ValueError(f"Artifact path escapes its bundle: {relative_path!r}")
    return path


def _load_bundle_at(project_root: pathlib.Path, bundle_root: pathlib.Path) -> BuildBundle:
    """Load and validate a bundle directory while its project lock is held."""
    bundle_root = pathlib.Path(bundle_root)
    manifest_path = bundle_root / paths.BUILD_MANIFEST_FILE.name
    if not bundle_root.exists():
        raise BuildError("missing", "", project_root)
    if not bundle_root.is_dir():
        raise BuildError("invalid", f"{paths.BUILD_OUTPUT_DIR} is not a directory", project_root)
    if not manifest_path.is_file():
        raise BuildError("incomplete", f"missing {paths.BUILD_MANIFEST_FILE.name}", project_root)

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


def load_build_bundle(project_root: str | pathlib.Path) -> BuildBundle:
    """Load and validate the active build without compiling or regenerating artifacts.

    Args:
        project_root: Root directory of the analytics project.

    Returns:
        A validated bundle containing the saved execution plan and artifact paths.

    Raises:
        BuildError: If the bundle is missing, incomplete, or invalid.
    """
    with read_build_bundle(project_root) as bundle:
        return bundle


@contextlib.contextmanager
def read_build_bundle(
    project_root: str | pathlib.Path,
) -> typing.Generator[BuildBundle]:
    """Load a validated bundle while holding a reader lock for the context lifetime."""
    project_root = pathlib.Path(project_root).resolve()
    with build_lock(project_root, exclusive=False):
        yield _load_bundle_at(project_root, project_root / paths.BUILD_OUTPUT_DIR)


def _normalize_features(features: FeatureSelection) -> list[str] | None:
    """Validate and normalize an optional nonempty output-feature selection."""
    if features is None:
        return None
    if isinstance(features, str):
        raise ValueError("features must be a collection of feature identifiers")
    normalized = list(features)
    if not normalized:
        raise ValueError("features must select at least one output feature")
    if any(not isinstance(feature, str) or not feature.strip() for feature in normalized):
        raise ValueError("feature identifiers must be nonempty strings")
    return sorted(set(normalized))


def _remove_path(path: pathlib.Path) -> None:
    """Remove a file, directory, or symlink created for publication."""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _publish_bundle(staging_root: pathlib.Path, target_root: pathlib.Path) -> None:
    """Replace the active bundle with staged output and restore it on failure."""
    backup_root = target_root.parent / f".build-backup-{uuid.uuid4().hex}"
    had_previous = target_root.exists() or target_root.is_symlink()
    if target_root.is_symlink():
        raise OSError(f"Refusing to replace a symlink at the active build path: {target_root}")
    if had_previous:
        try:
            os.replace(target_root, backup_root)
        except OSError as error:
            raise ProjectBuildError("publication", str(error)) from error
    try:
        os.replace(staging_root, target_root)
    except OSError as error:
        if had_previous:
            try:
                os.replace(backup_root, target_root)
            except OSError as restore_error:
                raise ProjectBuildError(
                    "publication",
                    f"{error}; failed to restore the previous bundle from "
                    f"{backup_root}: {restore_error}",
                ) from restore_error
        raise ProjectBuildError("publication", str(error)) from error
    if had_previous:
        try:
            _remove_path(backup_root)
        except OSError as error:
            raise ProjectBuildError(
                "cleanup",
                f"the new bundle was published, but the previous bundle at "
                f"{backup_root} could not be removed: {error}",
            ) from error


def build_project(
    project_root: str | pathlib.Path,
    *,
    entrypoint: str | None = None,
    source: SpecSource = None,
    features: FeatureSelection = None,
) -> BuildBundle:
    """Build and publish a complete spec, execution plan, and Explorer bundle.

    Args:
        project_root: Root directory of the analytics project.
        entrypoint: Optional ``module:attribute`` containing a ``PythonSpec``.
        source: Optional explicit spec JSON path.
        features: Optional output features to compile with their dependencies.

    Returns:
        The validated newly published bundle.

    Raises:
        BuildLockError: Another builder or active bundle reader holds the lock.
        ProjectBuildError: Source loading, compilation, generation, or publication fails.
    """
    root = pathlib.Path(project_root).resolve()
    try:
        selected_features = _normalize_features(features)
    except (ValueError, TypeError) as error:
        raise ProjectBuildError("feature selection", str(error)) from error
    try:
        spec_definition = load_spec_source(entrypoint, root, source=source)
    except (
        OSError,
        ValueError,
        ImportError,
        AttributeError,
        TypeError,
        SyntaxError,
    ) as error:
        raise ProjectBuildError("source loading", str(error)) from error

    with build_lock(root, exclusive=True, wait=False):
        generated_root = root / paths.GENERATED_DIR
        try:
            staging_root = pathlib.Path(
                tempfile.mkdtemp(prefix=".build-staging-", dir=generated_root)
            )
        except OSError as error:
            raise ProjectBuildError("staging setup", str(error)) from error
        try:
            try:
                execution_plan = compiler.Compiler(
                    spec_definition, features=selected_features
                ).compile()
            except (
                OSError,
                ValueError,
                ImportError,
                AttributeError,
                TypeError,
                SyntaxError,
            ) as error:
                raise ProjectBuildError("compilation", str(error)) from error

            explorer_root = staging_root / "explorer"
            try:
                # Explorer imports project path constants; defer it until package initialization.
                from uptimely.explorer import explorer as explorer_module

                spec.write_document(spec_definition, staging_root / "spec.json")
                execution_plan.export_json(staging_root / "execution_plan.json")
                explorer_module.Explorer(
                    spec_definition,
                    plan=execution_plan,
                    features=selected_features,
                ).create_html(explorer_root / "index.html")
            except (
                OSError,
                ValueError,
                ImportError,
                AttributeError,
                TypeError,
                SyntaxError,
                jinja2.TemplateError,
            ) as error:
                raise ProjectBuildError("artifact generation", str(error)) from error

            explorer_files = sorted(
                path.relative_to(explorer_root).as_posix()
                for path in explorer_root.rglob("*")
                if path.is_file()
            )
            try:
                manifest = BuildManifest(
                    schema_version=paths.BUILD_SCHEMA_VERSION,
                    uptimely_version=importlib.metadata.version("uptimely-core"),
                    features=selected_features,
                    artifacts=BuildArtifactPaths(
                        spec="spec.json",
                        execution_plan="execution_plan.json",
                        explorer="explorer",
                    ),
                    explorer_files=explorer_files,
                )
                (staging_root / paths.BUILD_MANIFEST_FILE.name).write_text(
                    json.dumps(manifest.model_dump(), indent=2),
                    encoding="utf-8",
                )
                _load_bundle_at(root, staging_root)
            except (
                OSError,
                ValueError,
                pydantic.ValidationError,
                importlib.metadata.PackageNotFoundError,
                BuildError,
            ) as error:
                raise ProjectBuildError("bundle validation", str(error)) from error

            _publish_bundle(staging_root, root / paths.BUILD_OUTPUT_DIR)
        finally:
            if staging_root.exists():
                try:
                    shutil.rmtree(staging_root)
                except OSError as error:
                    raise ProjectBuildError("staging cleanup", str(error)) from error

        return _load_bundle_at(root, root / paths.BUILD_OUTPUT_DIR)
