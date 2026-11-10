"""Root-bound operations for an analytics project."""

import contextlib
import pathlib

from .build import builder, bundle, models, source
from .build import features as feature_selection


class Project:
    """An analytics project rooted at a fixed, resolved filesystem path."""

    def __init__(self, root: str | pathlib.Path = ".") -> None:
        """Resolve the project root without loading or building artifacts.

        Args:
            root: Project directory, defaulting to the current working directory.
        """
        self.root = pathlib.Path(root).resolve()

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
    ) -> models.BuildBundle:
        """Build and publish the project's spec, plan, and Explorer snapshot.

        Args:
            python_spec: Optional ``module:attribute`` containing a Python Spec.
            json_spec: Optional explicit spec JSON path.
            features: Optional output features to compile with their dependencies.

        Returns:
            The validated newly published bundle.

        Raises:
            BuildLockError: Another builder or active bundle reader holds the lock.
            ProjectBuildError: Loading, compilation, generation, or publication fails.
        """
        return builder.build(
            self.root, python_spec=python_spec, json_spec=json_spec, features=features
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
        return bundle.load_build_bundle(self.root, validate=validate)

    def read_build_bundle(
        self, *, validate: bool = True
    ) -> contextlib.AbstractContextManager[models.BuildBundle]:
        """Return a context manager holding a reader lock while using the build.

        Args:
            validate: Run Spec semantic checks in addition to artifact and plan checks.

        Returns:
            A context manager yielding the validated saved build bundle.
        """
        return bundle.read_build_bundle(self.root, validate=validate)
