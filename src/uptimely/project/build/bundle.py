"""Loading and validating active build bundle artifacts."""

from __future__ import annotations

import contextlib
import json
import pathlib
import typing

import pydantic

from uptimely import spec
from uptimely.plan import models as plan_models
from uptimely.plan import serialization as plan_serialization
from uptimely.project import paths

from . import errors, locking, models


class BundleStore:
    """Load saved and staged bundles for a fixed project root."""

    def __init__(self, project_root: str | pathlib.Path) -> None:
        """Resolve the project root without reading artifacts or acquiring a lock."""
        self.root = pathlib.Path(project_root).resolve()

    def load(self, *, validate: bool = True) -> models.BuildBundle:
        """Load the active build, releasing its reader lock before returning.

        Args:
            validate: Run Spec semantic checks. Artifact and plan checks always run.

        Returns:
            A validated bundle containing the saved Spec, plan, and artifact paths.

        Raises:
            BuildError: The bundle is missing, incomplete, or invalid.
        """
        with self.read(validate=validate) as build_bundle:
            return build_bundle

    @contextlib.contextmanager
    def read(self, *, validate: bool = True) -> typing.Generator[models.BuildBundle]:
        """Load the active build while holding a reader lock.

        Args:
            validate: Run Spec semantic checks. All other bundle checks always run.

        Yields:
            The loaded bundle, protected by the reader lock for the context lifetime.
        """
        with locking.build_lock(self.root, exclusive=False):
            yield self.load_at(self.root / paths.BUILD_OUTPUT_DIR, validate=validate)

    def load_at(
        self,
        bundle_root: pathlib.Path,
        *,
        validate: bool = True,
        log_structure: bool = True,
    ) -> models.BuildBundle:
        """Load a saved or staged bundle while the caller holds its project lock.

        Args:
            bundle_root: Directory containing the saved bundle.
            validate: Run Spec semantic checks. Structural and artifact checks always run.
            log_structure: Emit Spec structural validation debug messages.

        Returns:
            The validated bundle at the supplied directory.

        Raises:
            BuildError: The bundle is missing, incomplete, or invalid.
        """
        bundle_root = pathlib.Path(bundle_root)
        if not bundle_root.exists():
            raise errors.BuildError("missing", "", self.root)
        if not bundle_root.is_dir():
            raise errors.BuildError(
                "invalid", f"{paths.BUILD_OUTPUT_DIR} is not a directory", self.root
            )

        manifest = self._load_manifest(bundle_root)
        spec_path, execution_plan_path = self._resolve_artifacts(bundle_root, manifest)
        self._validate_required_artifacts(bundle_root, spec_path, execution_plan_path)
        spec_definition = self._load_spec_definition(
            spec_path, validate=validate, log_structure=log_structure
        )
        execution_plan = self._load_execution_plan(execution_plan_path)

        return models.BuildBundle(
            project_root=self.root,
            root=bundle_root,
            manifest=manifest,
            spec_path=spec_path,
            spec_definition=spec_definition,
            execution_plan_path=execution_plan_path,
            execution_plan=execution_plan,
        )

    @staticmethod
    def _resolve_bundle_path(bundle_root: pathlib.Path, relative_path: str) -> pathlib.Path:
        """Resolve a declared path and reject resolutions outside its root."""
        path = (bundle_root / pathlib.PurePosixPath(relative_path)).resolve()
        if not path.is_relative_to(bundle_root.resolve()):
            raise ValueError(f"Artifact path escapes its bundle: {relative_path!r}")
        return path

    def _load_manifest(self, bundle_root: pathlib.Path) -> models.BuildManifest:
        manifest_path = bundle_root / paths.BUILD_MANIFEST_FILE.name
        if not manifest_path.is_file():
            raise errors.BuildError(
                "incomplete", f"missing {paths.BUILD_MANIFEST_FILE.name}", self.root
            )

        try:
            manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest = models.BuildManifest.model_validate(manifest_data)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            pydantic.ValidationError,
        ) as error:
            raise errors.BuildError(
                "invalid", f"cannot read build manifest: {error}", self.root
            ) from error
        return manifest

    def _resolve_artifacts(
        self, bundle_root: pathlib.Path, manifest: models.BuildManifest
    ) -> tuple[pathlib.Path, pathlib.Path]:
        try:
            spec_path = self._resolve_bundle_path(bundle_root, manifest.artifacts.spec)
            execution_plan_path = self._resolve_bundle_path(
                bundle_root, manifest.artifacts.execution_plan
            )
        except ValueError as error:
            raise errors.BuildError("invalid", str(error), self.root) from error
        return spec_path, execution_plan_path

    def _validate_required_artifacts(
        self,
        bundle_root: pathlib.Path,
        spec_path: pathlib.Path,
        execution_plan_path: pathlib.Path,
    ) -> None:
        for artifact_path in (spec_path, execution_plan_path):
            if not artifact_path.is_file():
                relative_path = artifact_path.relative_to(bundle_root.resolve())
                raise errors.BuildError(
                    "incomplete", f"missing artifact {relative_path}", self.root
                )

    def _load_execution_plan(self, execution_plan_path: pathlib.Path) -> plan_models.ExecutionPlan:
        try:
            return plan_serialization.from_json(execution_plan_path)
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
                "invalid", f"cannot load execution plan: {error}", self.root
            ) from error

    def _load_spec_definition(
        self,
        spec_path: pathlib.Path,
        *,
        validate: bool = True,
        log_structure: bool = True,
    ) -> spec.Spec:
        try:
            return spec.load_spec(spec_path, validate=validate, log_structure=log_structure)
        except (OSError, UnicodeDecodeError, ValueError, TypeError, AttributeError) as error:
            raise errors.BuildError("invalid", f"cannot load Spec: {error}", self.root) from error


def load_build_bundle(
    project_root: str | pathlib.Path, *, validate: bool = True
) -> models.BuildBundle:
    """Load the active build through a root-bound bundle store.

    Args:
        project_root: Root directory of the analytics project.
        validate: Run Spec semantic checks. Artifact and plan checks always run.

    Returns:
        The validated saved build bundle.

    Raises:
        BuildError: The bundle is missing, incomplete, or invalid.
    """
    return BundleStore(project_root).load(validate=validate)


def read_build_bundle(
    project_root: str | pathlib.Path, *, validate: bool = True
) -> contextlib.AbstractContextManager[models.BuildBundle]:
    """Return a context manager holding a reader lock on the active build.

    Args:
        project_root: Root directory of the analytics project.
        validate: Run Spec semantic checks. All other bundle checks always run.

    Returns:
        A context manager yielding the validated saved build bundle.
    """
    return BundleStore(project_root).read(validate=validate)
