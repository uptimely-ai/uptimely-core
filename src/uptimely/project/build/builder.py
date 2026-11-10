"""Build and publish the active spec, execution plan, and Explorer snapshot."""

from __future__ import annotations

import importlib.metadata
import json
import os
import pathlib
import shutil
import tempfile
import uuid

import pydantic

from uptimely import compiler, spec
from uptimely.explorer import presentation
from uptimely.plan import serialization as plan_serialization
from uptimely.project import paths
from uptimely.project.build import bundle, errors, locking, models
from uptimely.project.build import features as feature_selection
from uptimely.project.build import source as build_source

_SPEC_PROCESSING_ERRORS = (
    OSError,
    ValueError,
    ImportError,
    AttributeError,
    TypeError,
    SyntaxError,
)


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
            raise errors.ProjectBuildError("publication", str(error)) from error
    try:
        os.replace(staging_root, target_root)
    except OSError as error:
        if had_previous:
            try:
                os.replace(backup_root, target_root)
            except OSError as restore_error:
                raise errors.ProjectBuildError(
                    "publication",
                    f"{error}; failed to restore the previous bundle from "
                    f"{backup_root}: {restore_error}",
                ) from restore_error
        raise errors.ProjectBuildError("publication", str(error)) from error
    if had_previous:
        try:
            _remove_path(backup_root)
        except OSError as error:
            raise errors.ProjectBuildError(
                "cleanup",
                f"the new bundle was published, but the previous bundle at "
                f"{backup_root} could not be removed: {error}",
            ) from error


def _load_spec_definition(
    root: pathlib.Path,
    python_spec: str | None,
    json_spec: build_source.JsonSourceInput,
) -> spec.Spec:
    """Parse the source, deferring semantic validation to compilation."""
    try:
        return build_source.SpecSource(root).load(python_spec, json_spec, validate=False)
    except _SPEC_PROCESSING_ERRORS as error:
        raise errors.ProjectBuildError("source loading", str(error)) from error


def _compile_plan(
    spec_definition: spec.Spec,
    selected_features: list[str] | None,
) -> compiler.ExecutionPlan:
    """Compile a specification into its execution plan."""
    try:
        return compiler.Compiler().compile(spec_definition, features=selected_features)
    except _SPEC_PROCESSING_ERRORS as error:
        raise errors.ProjectBuildError("compilation", str(error)) from error


def _generate_artifacts(
    spec_definition: spec.Spec,
    execution_plan: compiler.ExecutionPlan,
    selected_features: list[str] | None,
    staging_root: pathlib.Path,
    project_root: pathlib.Path,
) -> str:
    """Write the spec and execution plan and prepare the Explorer snapshot."""
    try:
        spec.write_document(spec_definition, staging_root / "spec.json")
        plan_serialization.export_json(execution_plan, staging_root / "execution_plan.json")
        presentation_data = presentation.build_presentation_data(
            spec_definition,
            execution_plan,
            features=selected_features,
            validate_spec=False,
            project_root=project_root,
        )
        return presentation.serialize_presentation_data(presentation_data)
    except (
        OSError,
        ValueError,
        ImportError,
        AttributeError,
        TypeError,
        SyntaxError,
    ) as error:
        raise errors.ProjectBuildError("artifact generation", str(error)) from error


def _validate_staged_bundle(
    root: pathlib.Path,
    staging_root: pathlib.Path,
    selected_features: list[str] | None,
) -> None:
    """Write the bundle manifest and validate the staged spec and execution plan."""
    try:
        manifest = models.BuildManifest(
            build_version=models.BUILD_VERSION,
            uptimely_version=importlib.metadata.version("uptimely-core"),
            features=selected_features,
            artifacts=models.BuildArtifactPaths(
                spec="spec.json",
                execution_plan="execution_plan.json",
            ),
        )
        (staging_root / paths.BUILD_MANIFEST_FILE.name).write_text(
            json.dumps(manifest.model_dump(), indent=2),
            encoding="utf-8",
        )
        bundle.load_bundle_at(root, staging_root, validate=False, log_structure=False)
    except (
        OSError,
        ValueError,
        pydantic.ValidationError,
        importlib.metadata.PackageNotFoundError,
        errors.BuildError,
    ) as error:
        raise errors.ProjectBuildError("bundle validation", str(error)) from error


def _publish_explorer_snapshot(project_root: pathlib.Path, snapshot: str) -> None:
    """Atomically replace the saved Explorer snapshot after a successful build."""
    target = project_root / paths.EXPLORER_DATA_FILE
    temporary_path: pathlib.Path | None = None
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            prefix=f".{target.name}.",
            suffix=".tmp",
            dir=target.parent,
            delete=False,
        ) as temporary_file:
            temporary_path = pathlib.Path(temporary_file.name)
            temporary_file.write(snapshot)
        os.replace(temporary_path, target)
    except OSError as error:
        detail = str(error)
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError as cleanup_error:
                detail = f"{detail}; could not remove temporary snapshot: {cleanup_error}"
        raise errors.ProjectBuildError("Explorer snapshot publication", detail) from error


def _create_staging_root(generated_root: pathlib.Path) -> pathlib.Path:
    """Create a temporary directory for the next active bundle."""
    try:
        return pathlib.Path(tempfile.mkdtemp(prefix=".build-staging-", dir=generated_root))
    except OSError as error:
        raise errors.ProjectBuildError("staging setup", str(error)) from error


def _cleanup_staging_root(staging_root: pathlib.Path) -> None:
    """Remove temporary build output after success or failure."""
    if not staging_root.exists():
        return
    try:
        shutil.rmtree(staging_root)
    except OSError as error:
        raise errors.ProjectBuildError("staging cleanup", str(error)) from error


def build(
    project_root: str | pathlib.Path = ".",
    python_spec: str | None = None,
    json_spec: build_source.JsonSourceInput = None,
    features: feature_selection.FeatureSelection = None,
) -> models.BuildBundle:
    """Build and publish a spec, execution plan, and Explorer snapshot.

    Args:
        project_root: Root directory of the analytics project; defaults to the current directory.
        python_spec: Optional ``module:attribute`` containing a ``PythonSpec``.
        json_spec: Optional explicit spec JSON path.
        features: Optional output features to compile with their dependencies.

    Returns:
        The validated newly published bundle.

    Raises:
        BuildLockError: Another builder or active bundle reader holds the lock.
        ProjectBuildError: Source loading, compilation, generation, or publication fails.
    """
    root = pathlib.Path(project_root or ".").resolve()
    try:
        selected_features = feature_selection.normalize_features(features)
    except (ValueError, TypeError) as error:
        raise errors.ProjectBuildError("feature selection", str(error)) from error
    spec_definition = _load_spec_definition(root, python_spec, json_spec)

    with locking.build_lock(root, exclusive=True, wait=False):
        generated_root = root / paths.GENERATED_DIR
        staging_root = _create_staging_root(generated_root)
        try:
            execution_plan = _compile_plan(spec_definition, selected_features)
            snapshot = _generate_artifacts(
                spec_definition, execution_plan, selected_features, staging_root, root
            )
            _validate_staged_bundle(root, staging_root, selected_features)
            _publish_bundle(staging_root, root / paths.BUILD_OUTPUT_DIR)
            _publish_explorer_snapshot(root, snapshot)
        finally:
            _cleanup_staging_root(staging_root)

        return bundle.load_bundle_at(
            root, root / paths.BUILD_OUTPUT_DIR, validate=False, log_structure=False
        )
