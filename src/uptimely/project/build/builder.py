"""Build and publish a complete active build bundle."""

from __future__ import annotations

import importlib.metadata
import json
import os
import pathlib
import shutil
import tempfile
import uuid

import jinja2
import pydantic

from uptimely import compiler, spec
from uptimely.project import imports, paths
from uptimely.project.build import bundle, errors, locking, models
from uptimely.project.build import features as feature_selection
from uptimely.project.build import source as build_source

BuildBundle = models.BuildBundle
FeatureSelection = feature_selection.FeatureSelection

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
    """Load the project specification and report source errors by build stage."""
    try:
        return build_source.SpecSource(root).load(python_spec, json_spec)
    except _SPEC_PROCESSING_ERRORS as error:
        raise errors.ProjectBuildError("source loading", str(error)) from error


def _compile_plan(
    spec_definition: spec.Spec,
    selected_features: list[str] | None,
) -> compiler.ExecutionPlan:
    """Compile a specification into its execution plan."""
    try:
        return compiler.Compiler(spec_definition, features=selected_features).compile()
    except _SPEC_PROCESSING_ERRORS as error:
        raise errors.ProjectBuildError("compilation", str(error)) from error


def _generate_artifacts(
    spec_definition: spec.Spec,
    execution_plan: compiler.ExecutionPlan,
    selected_features: list[str] | None,
    staging_root: pathlib.Path,
) -> None:
    """Write the specification, execution plan, and Explorer site."""
    try:
        # Explorer imports project path constants; defer it until package initialization.
        from uptimely.explorer import explorer as explorer_module

        spec.write_document(spec_definition, staging_root / "spec.json")
        execution_plan.export_json(staging_root / "execution_plan.json")
        explorer_module.Explorer(
            spec_definition,
            plan=execution_plan,
            features=selected_features,
        ).create_html(staging_root / "explorer" / "index.html")
    except (
        OSError,
        ValueError,
        ImportError,
        AttributeError,
        TypeError,
        SyntaxError,
        jinja2.TemplateError,
    ) as error:
        raise errors.ProjectBuildError("artifact generation", str(error)) from error


def _validate_staged_bundle(
    root: pathlib.Path,
    staging_root: pathlib.Path,
    selected_features: list[str] | None,
) -> None:
    """Write the bundle manifest and validate all staged artifacts."""
    explorer_root = staging_root / "explorer"
    explorer_files = sorted(
        path.relative_to(explorer_root).as_posix()
        for path in explorer_root.rglob("*")
        if path.is_file()
    )
    try:
        manifest = models.BuildManifest(
            build_version=models.BUILD_VERSION,
            uptimely_version=importlib.metadata.version("uptimely-core"),
            features=selected_features,
            artifacts=models.BuildArtifactPaths(
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
        bundle.load_bundle_at(root, staging_root)
    except (
        OSError,
        ValueError,
        pydantic.ValidationError,
        importlib.metadata.PackageNotFoundError,
        errors.BuildError,
    ) as error:
        raise errors.ProjectBuildError("bundle validation", str(error)) from error


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


def build_project(
    project_root: str | pathlib.Path,
    python_spec: str | None = None,
    json_spec: build_source.JsonSourceInput = None,
    features: FeatureSelection = None,
) -> BuildBundle:
    """Build and publish a complete spec, execution plan, and Explorer bundle.

    Args:
        project_root: Root directory of the analytics project.
        python_spec: Optional ``module:attribute`` containing a ``PythonSpec``.
        json_spec: Optional explicit spec JSON path.
        features: Optional output features to compile with their dependencies.

    Returns:
        The validated newly published bundle.

    Raises:
        BuildLockError: Another builder or active bundle reader holds the lock.
        ProjectBuildError: Source loading, compilation, generation, or publication fails.
    """
    root = pathlib.Path(project_root).resolve()
    try:
        selected_features = feature_selection.normalize_features(features)
    except (ValueError, TypeError) as error:
        raise errors.ProjectBuildError("feature selection", str(error)) from error
    imports.prepare_imports(root)
    spec_definition = _load_spec_definition(root, python_spec, json_spec)

    with locking.build_lock(root, exclusive=True, wait=False):
        generated_root = root / paths.GENERATED_DIR
        staging_root = _create_staging_root(generated_root)
        try:
            execution_plan = _compile_plan(spec_definition, selected_features)
            _generate_artifacts(spec_definition, execution_plan, selected_features, staging_root)
            _validate_staged_bundle(root, staging_root, selected_features)
            _publish_bundle(staging_root, root / paths.BUILD_OUTPUT_DIR)
        finally:
            _cleanup_staging_root(staging_root)

        return bundle.load_bundle_at(root, root / paths.BUILD_OUTPUT_DIR)
