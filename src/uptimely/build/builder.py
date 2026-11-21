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
from uptimely.codebase import packaging
from uptimely.codebase.python import packaging as python_packaging
from uptimely.explorer import presentation
from uptimely.plan import serialization as plan_serialization
from uptimely.project import defaults, paths, python_imports
from uptimely.project import spec_source as project_spec_source

from . import bundle, errors, locking, models
from . import features as feature_selection

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

    def __init__(
        self,
        project_root: str | pathlib.Path = defaults.DEFAULT_PROJECT_ROOT,
        *,
        code_packager: packaging.CodePackager | None = None,
    ) -> None:
        """Resolve the project root without loading or generating artifacts.

        Args:
            project_root: Project directory, defaulting to the current directory.
            code_packager: Implementation artifact provider, defaulting to Python.
        """
        self.root = pathlib.Path(project_root).resolve()
        self._store = bundle.BundleStore(self.root)
        self._code_packager = (
            python_packaging.PythonPackager() if code_packager is None else code_packager
        )

    def build(
        self,
        *,
        python_spec: str | None = None,
        json_spec: project_spec_source.JsonSourceInput = None,
        features: feature_selection.FeatureSelection = None,
        src_path: pathlib.Path | None = None,
        runtime_path: str | pathlib.Path = packaging.RUNTIME_DIR,
        runtime_type: str | None = None,
    ) -> models.BuildBundle:
        """Build and publish a spec, execution plan, and Explorer snapshot.

        Args:
            python_spec: Optional ``module:attribute`` containing a Python Spec.
            json_spec: Optional explicit spec JSON path, relative to the project root
                unless absolute.
            features: Optional output features to compile with their dependencies.
            src_path: Optional source directory, relative to the project root unless absolute.
                Defaults to the project source path.
            runtime_path: Runtime definition directory, relative to the project root unless
                absolute. Defaults to ``runtime``.
            runtime_type: Project runtime type. Defaults to the staged runtime type,
                or Python if the packager does not provide one.

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
            spec_source = project_spec_source.SpecSourceResolver(self.root).resolve(
                python_spec, json_spec
            )
        except _SPEC_PROCESSING_ERRORS as error:
            raise errors.ProjectBuildError("source loading", str(error)) from error
        resolved_src_path = python_imports.resolve_src_path(self.root, src_path)
        with (
            locking.build_lock(self.root, exclusive=True, wait=False),
            python_imports.expose(self.root, src_path=src_path),
        ):
            spec_definition = self._load_spec_definition(spec_source)
            staging_root = self._create_staging_root()
            try:
                execution_plan = self._compile_plan(spec_definition, selected_features)
                code_artifacts = self._generate_artifacts(
                    spec_definition,
                    execution_plan,
                    selected_features,
                    staging_root,
                    resolved_src_path,
                    self.root / runtime_path,
                )
                self._validate_staged_bundle(
                    staging_root,
                    selected_features,
                    resolved_src_path,
                    spec_source.display_name,
                    code_artifacts,
                    runtime_type,
                )
                self._publish_bundle(staging_root)
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

    @staticmethod
    def _load_spec_definition(source: project_spec_source.ResolvedSpecSource) -> spec.Spec:
        """Load a resolved source, deferring semantic validation to compilation."""
        try:
            return project_spec_source.load_spec_source(source, validate=False)
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
        resolved_src_path: pathlib.Path,
        runtime_root: pathlib.Path,
    ) -> packaging.StagedCode:
        """Stage portable inputs and the Explorer snapshot."""
        try:
            spec.write_document(spec_definition, staging_root / paths.BUILD_SPEC_FILE.name)
            plan_serialization.export_json(
                execution_plan, staging_root / paths.BUILD_EXECUTION_PLAN_FILE.name
            )
            code_artifacts = self._code_packager.stage(
                self.root, resolved_src_path, staging_root, runtime_root
            )
            presentation_data = presentation.build_presentation_data(
                spec_definition,
                execution_plan,
                features=selected_features,
                validate_spec=False,
                project_root=self.root,
                src_path=resolved_src_path if resolved_src_path.is_dir() else None,
            )
            (staging_root / paths.EXPLORER_DATA_FILE.name).write_text(
                presentation.serialize_presentation_data(presentation_data), encoding="utf-8"
            )
            return code_artifacts
        except _SPEC_PROCESSING_ERRORS as error:
            raise errors.ProjectBuildError("artifact generation", str(error)) from error

    def _validate_staged_bundle(
        self,
        staging_root: pathlib.Path,
        selected_features: list[str] | None,
        resolved_src_path: pathlib.Path,
        spec_source: str,
        code_artifacts: packaging.StagedCode,
        runtime_type: str | None,
    ) -> None:
        """Write the bundle manifest and validate the staged spec and execution plan."""
        try:
            staged_runtime = code_artifacts.runtime
            if (
                runtime_type is not None
                and staged_runtime is not None
                and runtime_type != staged_runtime.type
            ):
                raise ValueError(
                    f"Configured runtime type {runtime_type!r} does not match "
                    f"packaged runtime type {staged_runtime.type!r}"
                )
            selected_runtime_type = runtime_type
            if selected_runtime_type is None:
                selected_runtime_type = (
                    staged_runtime.type
                    if staged_runtime is not None
                    else python_packaging.RUNTIME_TYPE
                )
            try:
                manifest_src_path = resolved_src_path.relative_to(self.root).as_posix()
            except ValueError:
                manifest_src_path = str(resolved_src_path)
            manifest = models.BuildManifest(
                build_version=models.BUILD_VERSION,
                uptimely_version=importlib.metadata.version("uptimely-core"),
                features=selected_features,
                src_path=manifest_src_path,
                spec_source=spec_source,
                artifacts=models.BuildArtifactPaths(
                    spec=paths.BUILD_SPEC_FILE.name,
                    execution_plan=paths.BUILD_EXECUTION_PLAN_FILE.name,
                    explorer="explorer.json",
                    packages=code_artifacts.packages,
                    runtime=packaging.CodeRuntime(
                        type=selected_runtime_type,
                        path=staged_runtime.path if staged_runtime is not None else None,
                    ),
                ),
            )
            code_artifacts.validate_layout(staging_root)
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

    def _create_staging_root(self) -> pathlib.Path:
        """Create a temporary directory for the next active bundle."""
        try:
            return pathlib.Path(
                tempfile.mkdtemp(prefix=".build-staging-", dir=self.root / paths.ARTIFACTS_DIR)
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
    project_root: str | pathlib.Path = defaults.DEFAULT_PROJECT_ROOT,
    python_spec: str | None = None,
    json_spec: project_spec_source.JsonSourceInput = None,
    features: feature_selection.FeatureSelection = None,
    src_path: pathlib.Path | None = None,
    *,
    runtime_path: str | pathlib.Path = packaging.RUNTIME_DIR,
    runtime_type: str | None = None,
) -> models.BuildBundle:
    """Build and publish project artifacts through a root-bound builder.

    Args:
        project_root: Project directory, defaulting to the current directory.
        python_spec: Optional ``module:attribute`` containing a Python Spec.
        json_spec: Optional explicit spec JSON path, relative to the project root
            unless absolute.
        features: Optional output features to compile with their dependencies.
        src_path: Optional source directory, relative to the project root unless absolute.
            Defaults to ``src``.
        runtime_path: Runtime definition directory, relative to the project root unless
            absolute. Defaults to ``runtime``.
        runtime_type: Project runtime type. Defaults to the staged runtime type,
            or Python if the packager does not provide one.

    Returns:
        The validated newly published bundle.

    Raises:
        BuildLockError: Another builder or active bundle reader holds the lock.
        ProjectBuildError: Loading, compilation, generation, or publication fails.
    """
    return ProjectBuilder(project_root).build(
        python_spec=python_spec,
        json_spec=json_spec,
        features=features,
        src_path=src_path,
        runtime_path=runtime_path,
        runtime_type=runtime_type,
    )
