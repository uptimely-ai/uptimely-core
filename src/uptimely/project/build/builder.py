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

from . import bundle, errors, locking, models
from . import features as feature_selection
from . import source as build_source

_SPEC_PROCESSING_ERRORS = (
    OSError,
    ValueError,
    ImportError,
    AttributeError,
    TypeError,
    SyntaxError,
)


class ProjectBuilder:
    """Build project artifacts without retaining per-build mutable state."""

    def __init__(self, project_root: str | pathlib.Path = ".") -> None:
        """Resolve the project root without loading or generating artifacts."""
        self.root = pathlib.Path(project_root).resolve()
        self._store = bundle.BundleStore(self.root)

    def build(
        self,
        *,
        python_spec: str | None = None,
        json_spec: build_source.JsonSourceInput = None,
        features: feature_selection.FeatureSelection = None,
        src_path: pathlib.Path | None = None,
    ) -> models.BuildBundle:
        """Build and publish a spec, execution plan, and Explorer snapshot.

        Args:
            python_spec: Optional ``module:attribute`` containing a Python Spec.
            json_spec: Optional explicit spec JSON path.
            features: Optional output features to compile with their dependencies.
            src_path: Optional source directory, relative to the project root unless absolute.
                Defaults to ``src``.

        Returns:
            The validated newly published bundle.

        Raises:
            BuildLockError: Another builder or active bundle reader holds the lock.
            ProjectBuildError: Loading, compilation, generation, or publication fails.
        """
        try:
            selected_features = feature_selection.normalize_features(features)
        except (ValueError, TypeError) as error:
            raise errors.ProjectBuildError("feature selection", str(error)) from error
        try:
            build_source.SpecSource(self.root).resolve(python_spec, json_spec)
        except _SPEC_PROCESSING_ERRORS as error:
            raise errors.ProjectBuildError("source loading", str(error)) from error
        with (
            locking.build_lock(self.root, exclusive=True, wait=False),
            build_source.project_source_path(self.root, src_path=src_path),
        ):
            spec_definition = self._load_spec_definition(python_spec, json_spec)
            staging_root = self._create_staging_root()
            try:
                execution_plan = self._compile_plan(spec_definition, selected_features)
                snapshot = self._generate_artifacts(
                    spec_definition, execution_plan, selected_features, staging_root, src_path
                )
                self._validate_staged_bundle(staging_root, selected_features)
                self._publish_bundle(staging_root)
                self._publish_explorer_snapshot(snapshot)
            finally:
                self._cleanup_staging_root(staging_root)

            return self._store.load_at(
                self.root / paths.BUILD_OUTPUT_DIR, validate=False, log_structure=False
            )

    @staticmethod
    def _remove_path(path: pathlib.Path) -> None:
        """Remove a file, directory, or symlink created for publication."""
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.exists():
            shutil.rmtree(path)

    def _publish_bundle(self, staging_root: pathlib.Path) -> None:
        """Replace the active bundle with staged output and restore it on failure."""
        target_root = self.root / paths.BUILD_OUTPUT_DIR
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
                        f"{error}. Failed to restore the previous bundle from "
                        f"{backup_root}: {restore_error}",
                    ) from restore_error
            raise errors.ProjectBuildError("publication", str(error)) from error
        if had_previous:
            try:
                self._remove_path(backup_root)
            except OSError as error:
                raise errors.ProjectBuildError(
                    "cleanup",
                    f"the new bundle was published, but the previous bundle at "
                    f"{backup_root} could not be removed: {error}",
                ) from error

    def _load_spec_definition(
        self, python_spec: str | None, json_spec: build_source.JsonSourceInput
    ) -> spec.Spec:
        """Parse the source, deferring semantic validation to compilation."""
        try:
            return build_source.SpecSource(self.root).load(python_spec, json_spec, validate=False)
        except _SPEC_PROCESSING_ERRORS as error:
            raise errors.ProjectBuildError("source loading", str(error)) from error

    @staticmethod
    def _compile_plan(
        spec_definition: spec.Spec, selected_features: list[str] | None
    ) -> compiler.ExecutionPlan:
        """Compile a specification into its execution plan."""
        try:
            return compiler.Compiler().compile(spec_definition, features=selected_features)
        except _SPEC_PROCESSING_ERRORS as error:
            raise errors.ProjectBuildError("compilation", str(error)) from error

    def _generate_artifacts(
        self,
        spec_definition: spec.Spec,
        execution_plan: compiler.ExecutionPlan,
        selected_features: list[str] | None,
        staging_root: pathlib.Path,
        src_path: pathlib.Path | None,
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
                project_root=self.root,
                src_path=src_path,
            )
            return presentation.serialize_presentation_data(presentation_data)
        except _SPEC_PROCESSING_ERRORS as error:
            raise errors.ProjectBuildError("artifact generation", str(error)) from error

    def _validate_staged_bundle(
        self, staging_root: pathlib.Path, selected_features: list[str] | None
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
            self._store.load_at(staging_root, validate=False, log_structure=False)
        except (
            OSError,
            ValueError,
            pydantic.ValidationError,
            importlib.metadata.PackageNotFoundError,
            errors.BuildError,
        ) as error:
            raise errors.ProjectBuildError("bundle validation", str(error)) from error

    def _publish_explorer_snapshot(self, snapshot: str) -> None:
        """Atomically replace the saved Explorer snapshot after a successful build."""
        target = self.root / paths.EXPLORER_DATA_FILE
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
                    detail = f"{detail}. Could not remove temporary snapshot: {cleanup_error}"
            raise errors.ProjectBuildError("Explorer snapshot publication", detail) from error

    def _create_staging_root(self) -> pathlib.Path:
        """Create a temporary directory for the next active bundle."""
        try:
            return pathlib.Path(
                tempfile.mkdtemp(prefix=".build-staging-", dir=self.root / paths.GENERATED_DIR)
            )
        except OSError as error:
            raise errors.ProjectBuildError("staging setup", str(error)) from error

    @staticmethod
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
    src_path: pathlib.Path | None = None,
) -> models.BuildBundle:
    """Build and publish project artifacts through a root-bound builder.

    Args:
        project_root: Project directory, defaulting to the current directory.
        python_spec: Optional ``module:attribute`` containing a Python Spec.
        json_spec: Optional explicit spec JSON path.
        features: Optional output features to compile with their dependencies.
        src_path: Optional source directory, relative to the project root unless absolute.
            Defaults to ``src``.

    Returns:
        The validated newly published bundle.

    Raises:
        BuildLockError: Another builder or active bundle reader holds the lock.
        ProjectBuildError: Loading, compilation, generation, or publication fails.
    """
    return ProjectBuilder(project_root).build(
        python_spec=python_spec, json_spec=json_spec, features=features, src_path=src_path
    )
