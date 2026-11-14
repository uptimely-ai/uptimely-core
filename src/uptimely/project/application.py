"""Application entry point for an analytics project."""

from __future__ import annotations

import contextlib
import pathlib
import tomllib

from uptimely import engine as engine_module

from . import config, paths
from .build import builder, bundle, models, source
from .build import features as feature_selection


class Uptimely:
    """Entry point for an analytics project at a fixed filesystem path."""

    def __init__(
        self, root: str | pathlib.Path = ".", *, config_path: str | pathlib.Path | None = None
    ) -> None:
        """Resolve the project root and load its configuration once.

        Args:
            root: Project directory, defaulting to the current working directory.
            config_path: Explicit TOML file, relative to the current directory if relative.
                Defaults to ``uptimely.toml`` under the project root.
        """
        self.root = pathlib.Path(root).resolve()
        self.config_path = (
            self.root / paths.CONFIG_FILE
            if config_path is None
            else pathlib.Path(config_path).resolve()
        )
        if config_path is None and not self.config_path.exists():
            self.config = config.ProjectConfig()
        else:
            with self.config_path.open("rb") as file:
                self.config = config.ProjectConfig.model_validate(tomllib.load(file))

    def create_engine(self, build: models.BuildBundle) -> engine_module.Engine:
        """Create an engine with this project's configuration.

        Args:
            build: Build bundle belonging to this project.

        Returns:
            Engine configured for the build.

        Raises:
            ValueError: The bundle belongs to a different project.
        """
        if build.project_root.resolve() != self.root:
            raise ValueError("Build bundle belongs to a different project")
        return engine_module.Engine(
            build,
            self.config.engine,
            self.config.params.root,
            paths=self.config.paths.root,
        )

    def resolve_path(self, path: pathlib.Path | None, default: pathlib.Path) -> pathlib.Path:
        """Preserve an explicit path or place a default beneath the project root.

        Args:
            path: Explicit path to preserve, including relative paths.
            default: Default project-relative path.

        Returns:
            The explicit path or the default path joined to this project's root.
        """
        return path if path is not None else self.root / default

    def build(
        self,
        *,
        python_spec: str | None = None,
        json_spec: source.JsonSourceInput = None,
        features: feature_selection.FeatureSelection = None,
        src_path: pathlib.Path | None = None,
    ) -> models.BuildBundle:
        """Build and publish the project's spec, plan, and Explorer snapshot.

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
        return builder.ProjectBuilder(self.root).build(
            python_spec=python_spec,
            json_spec=json_spec,
            features=features,
            src_path=src_path,
        )

    def run(
        self,
        *,
        validate: bool = False,
        preview_rows: int = engine_module.config.DEFAULT_PREVIEW_ROWS,
        operator: tuple[str, str] | None = None,
        src_path: pathlib.Path | None = None,
    ) -> engine_module.ExecutionResult:
        """Run the saved build without rebuilding it.

        Args:
            validate: Validate inputs and dataframe contracts at every step.
            preview_rows: Positive maximum sample size per profile.
            operator: Optional profile and operator IDs selecting an operator
                and its saved prerequisites.
            src_path: Optional Python source directory, relative to the project root
                unless absolute. Defaults to ``src``.

        Returns:
            Execution results, including any invocation failures.

        Raises:
            BuildError: The saved build is missing, incomplete, or invalid.
            BuildLockError: A builder holds the project build lock.
            OSError: Run artifacts cannot be persisted.
            ValueError: The preview row limit or requested operator is invalid.
        """
        with self.read_build_bundle() as build:
            return self.create_engine(build).run(
                validate=validate,
                preview_rows=preview_rows,
                operator=operator,
                src_path=src_path,
            )

    def load_build_bundle(self, *, validate: bool = True) -> models.BuildBundle:
        """Load the saved build without holding a reader lock after loading.

        Args:
            validate: Run Spec semantic checks in addition to artifact and plan checks.

        Returns:
            The validated saved build bundle.

        Raises:
            BuildError: The saved build is missing, incomplete, or invalid.
        """
        return bundle.BundleStore(self.root).load(validate=validate)

    def read_build_bundle(
        self, *, validate: bool = True
    ) -> contextlib.AbstractContextManager[models.BuildBundle]:
        """Return a context manager holding a reader lock while using the build.

        Args:
            validate: Run Spec semantic checks in addition to artifact and plan checks.

        Returns:
            A context manager yielding the validated saved build bundle.
        """
        return bundle.BundleStore(self.root).read(validate=validate)
