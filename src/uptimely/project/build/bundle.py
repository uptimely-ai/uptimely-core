"""Loading and validating active build bundle artifacts."""

from __future__ import annotations

import contextlib
import json
import pathlib
import typing

import pydantic

from uptimely.compiler.plan import models as plan_models
from uptimely.project import paths
from uptimely.project.build import errors, locking, models


def _resolve_bundle_path(
    bundle_root: pathlib.Path, relative_path: str, *, containment_root: pathlib.Path | None = None
) -> pathlib.Path:
    """Resolve a declared path and reject resolutions outside its root."""
    path = (bundle_root / pathlib.PurePosixPath(relative_path)).resolve()
    allowed_root = (containment_root or bundle_root).resolve()
    if not path.is_relative_to(allowed_root):
        raise ValueError(f"Artifact path escapes its bundle: {relative_path!r}")
    return path


def _load_manifest(bundle_root: pathlib.Path, project_root: pathlib.Path) -> models.BuildManifest:
    manifest_path = bundle_root / paths.BUILD_MANIFEST_FILE.name
    if not manifest_path.is_file():
        raise errors.BuildError(
            "incomplete", f"missing {paths.BUILD_MANIFEST_FILE.name}", project_root
        )

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest = models.BuildManifest.model_validate(manifest_data)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, pydantic.ValidationError) as error:
        raise errors.BuildError(
            "invalid", f"cannot read build manifest: {error}", project_root
        ) from error
    return manifest


def _resolve_artifacts(
    bundle_root: pathlib.Path,
    manifest: models.BuildManifest,
    project_root: pathlib.Path,
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    try:
        spec_path = _resolve_bundle_path(bundle_root, manifest.artifacts.spec)
        execution_plan_path = _resolve_bundle_path(bundle_root, manifest.artifacts.execution_plan)
        explorer_path = _resolve_bundle_path(bundle_root, manifest.artifacts.explorer)
    except ValueError as error:
        raise errors.BuildError("invalid", str(error), project_root) from error
    return spec_path, execution_plan_path, explorer_path


def _validate_required_artifacts(
    bundle_root: pathlib.Path,
    spec_path: pathlib.Path,
    execution_plan_path: pathlib.Path,
    project_root: pathlib.Path,
) -> None:
    for artifact_path in (spec_path, execution_plan_path):
        if not artifact_path.is_file():
            relative_path = artifact_path.relative_to(bundle_root.resolve())
            raise errors.BuildError("incomplete", f"missing artifact {relative_path}", project_root)


def _validate_explorer_inventory(
    explorer_path: pathlib.Path,
    manifest: models.BuildManifest,
    project_root: pathlib.Path,
) -> None:
    if not explorer_path.is_dir():
        raise errors.BuildError(
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
        raise errors.BuildError("incomplete", str(error), project_root) from error


def _load_execution_plan(
    execution_plan_path: pathlib.Path, project_root: pathlib.Path
) -> plan_models.ExecutionPlan:
    try:
        return plan_models.ExecutionPlan.from_json(execution_plan_path)
    except (
        OSError,
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
    ) as error:
        raise errors.BuildError(
            "invalid", f"cannot load execution plan: {error}", project_root
        ) from error


def load_bundle_at(project_root: pathlib.Path, bundle_root: pathlib.Path) -> models.BuildBundle:
    """Load and validate a bundle directory while its project lock is held."""
    bundle_root = pathlib.Path(bundle_root)
    if not bundle_root.exists():
        raise errors.BuildError("missing", "", project_root)
    if not bundle_root.is_dir():
        raise errors.BuildError(
            "invalid", f"{paths.BUILD_OUTPUT_DIR} is not a directory", project_root
        )

    manifest = _load_manifest(bundle_root, project_root)
    spec_path, execution_plan_path, explorer_path = _resolve_artifacts(
        bundle_root, manifest, project_root
    )
    _validate_required_artifacts(bundle_root, spec_path, execution_plan_path, project_root)
    _validate_explorer_inventory(explorer_path, manifest, project_root)
    execution_plan = _load_execution_plan(execution_plan_path, project_root)

    return models.BuildBundle(
        project_root=project_root.resolve(),
        root=bundle_root,
        manifest=manifest,
        spec_path=spec_path,
        execution_plan_path=execution_plan_path,
        explorer_path=explorer_path,
        execution_plan=execution_plan,
    )


def load_build_bundle(project_root: str | pathlib.Path) -> models.BuildBundle:
    """Load and validate the active build without compiling or regenerating artifacts.

    Args:
        project_root: Root directory of the analytics project.

    Returns:
        A validated bundle containing the saved execution plan and artifact paths.

    Raises:
        BuildError: If the bundle is missing, incomplete, or invalid.
    """
    with read_build_bundle(project_root) as build_bundle:
        return build_bundle


@contextlib.contextmanager
def read_build_bundle(
    project_root: str | pathlib.Path,
) -> typing.Generator[models.BuildBundle]:
    """Load a validated bundle while holding a reader lock for the context lifetime."""
    project_root = pathlib.Path(project_root).resolve()
    with locking.build_lock(project_root, exclusive=False):
        yield load_bundle_at(project_root, project_root / paths.BUILD_OUTPUT_DIR)
