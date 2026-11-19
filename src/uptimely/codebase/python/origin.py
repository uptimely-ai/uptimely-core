"""Identify installed package and source-file ownership for Python entrypoints."""

from __future__ import annotations

import dataclasses
import functools
import importlib.metadata
import inspect
import pathlib
import sys
import typing


@functools.lru_cache(maxsize=1)
def _package_distributions(
    _path_snapshot: tuple[str, ...],  # pyright: ignore[reportUnusedParameter]
) -> dict[str, list[str]]:
    """Cache the index by import path; packages_distributions reads sys.path itself."""
    return importlib.metadata.packages_distributions()


@dataclasses.dataclass(frozen=True)
class PackageOrigin:
    """Installed distribution metadata associated with an entrypoint module."""

    distribution: str | None
    version: str | None
    top_level_package: str | None = dataclasses.field(default=None, compare=False)
    distribution_candidates: tuple[str, ...] = dataclasses.field(default=(), compare=False)

    def to_dict(self) -> dict[str, str | None]:
        """Return portable distribution metadata, excluding lookup diagnostics."""
        return {
            "distribution": self.distribution,
            "version": self.version,
        }

    def __str__(self) -> str:
        """Return package information suitable for diagnostics."""
        if self.distribution is None:
            return "unavailable"
        return (
            f"{self.distribution}=={self.version}"
            if self.version is not None
            else self.distribution
        )

    @classmethod
    def read(cls, module_path: str) -> PackageOrigin:
        """Read installed distribution metadata without importing the module."""
        top_level_package = cls._top_level_package(module_path)
        distribution_candidates = cls._distribution_candidates(top_level_package)
        distribution_name = cls._single_distribution(top_level_package, distribution_candidates)
        if distribution_name is None:
            return cls(
                distribution=None,
                version=None,
                top_level_package=top_level_package,
                distribution_candidates=distribution_candidates,
            )

        distribution = importlib.metadata.distribution(distribution_name)
        return cls(
            distribution=distribution.metadata.get("Name", distribution_name),
            version=distribution.version,
            top_level_package=top_level_package,
            distribution_candidates=distribution_candidates,
        )

    @staticmethod
    def _top_level_package(module_path: str) -> str:
        """Return the top-level package name from a dotted module path."""
        return module_path.partition(".")[0]

    @staticmethod
    def _distribution_candidates(top_level_package: str) -> tuple[str, ...]:
        """Return unique installed distributions for a top-level package."""
        distributions = _package_distributions(tuple(sys.path)).get(top_level_package, [])
        return tuple(sorted(set(distributions), key=str.casefold))

    @staticmethod
    def invalidate_cache() -> None:
        """Refresh the shared package index for future origin reads."""
        _package_distributions.cache_clear()

    @staticmethod
    def _single_distribution(
        top_level_package: str, distribution_candidates: tuple[str, ...]
    ) -> str | None:
        """Return the sole matching distribution, rejecting ambiguous namespaces."""
        if len(distribution_candidates) > 1:
            raise ValueError(
                f"Ambiguous installed package namespace {top_level_package!r}: "
                f"{', '.join(distribution_candidates)}"
            )
        return distribution_candidates[0] if distribution_candidates else None


@dataclasses.dataclass(frozen=True)
class SourceOrigin:
    """Ownership of a callable's implementation file relative to a project."""

    kind: typing.Literal["project", "third_party", "unknown"]
    distribution: str | None = None


def read_source_origin(
    implementation: typing.Callable[..., typing.Any],
    project_root: pathlib.Path | None,
) -> SourceOrigin:
    """Classify a callable implementation as project or installed code.

    Args:
        implementation: Loaded callable to classify.
        project_root: Project directory, or None when classification is unavailable.

    Returns:
        Verified source origin and, for installed code, the distribution name.
    """
    if project_root is None:
        return SourceOrigin("unknown")
    implementation = inspect.unwrap(implementation)
    implementation_module = inspect.getmodule(implementation)
    source_file = getattr(implementation_module, "__file__", None)
    if implementation_module is None or source_file is None:
        return SourceOrigin("unknown")
    source_path = pathlib.Path(source_file).resolve()
    top_level = PackageOrigin._top_level_package(implementation_module.__name__)
    for name in PackageOrigin._distribution_candidates(top_level):
        distribution = importlib.metadata.distribution(name)
        if distribution.files is not None and any(
            pathlib.Path(file.locate()).resolve() == source_path for file in distribution.files
        ):
            return SourceOrigin("third_party", distribution.metadata.get("Name", name))
    if source_path.is_relative_to(project_root.resolve()):
        return SourceOrigin("project")
    return SourceOrigin("unknown")
