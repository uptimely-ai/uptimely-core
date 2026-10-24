"""Load Python function entrypoints and read their annotated signatures."""

from __future__ import annotations

import dataclasses
import functools
import importlib
import importlib.metadata
import inspect
import pathlib
import sys
import types
import typing


@functools.lru_cache(maxsize=1)
def _package_distributions(
    _path_snapshot: tuple[str, ...],  # pyright: ignore[reportUnusedParameter]
) -> dict[str, list[str]]:
    """Cache the index by import path; packages_distributions reads sys.path itself."""
    return importlib.metadata.packages_distributions()


def _is_valid_qualified_name(name: str) -> bool:
    """Return whether a dotted name contains only Python identifiers."""
    return bool(name.strip()) and all(part.isidentifier() for part in name.split("."))


@dataclasses.dataclass(frozen=True)
class PackageProvenance:
    """Installed distribution metadata associated with an entrypoint module."""

    distribution: str | None
    version: str | None
    top_level_package: str | None = dataclasses.field(default=None, compare=False)
    distribution_candidates: tuple[str, ...] = dataclasses.field(default=(), compare=False)

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
    def read(cls, module_path: str) -> PackageProvenance:
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
        """Refresh the shared package index for future provenance reads.

        Package metadata already cached on existing Module instances is unchanged.
        """
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
class Module:
    """Represent and load an importable Python module."""

    location: str

    def __post_init__(self) -> None:
        location = self.location
        if not isinstance(location, str):
            raise TypeError("Module location must be a string")
        if not self.is_valid_location(location):
            raise ValueError("Module location must be an importable dotted module name")

    @staticmethod
    def is_valid_location(location: str) -> bool:
        """Return whether a string is an importable dotted module name."""
        return (
            bool(location.strip())
            and "/" not in location
            and "\\" not in location
            and not location.endswith(".py")
            and all(part.isidentifier() for part in location.split("."))
        )

    @functools.cached_property
    def package(self) -> PackageProvenance:
        """Return installed package provenance without importing this module."""
        return PackageProvenance.read(self.location)

    @property
    def source_file(self) -> str:
        """Return the loaded module's file path.

        Accessing this property imports and executes the module if needed.

        Raises:
            ValueError: The module does not identify a source file.
        """
        source_file = getattr(self.load(), "__file__", None)
        if source_file is None:
            raise ValueError(f"Python module {self.location!r} does not identify its source file")
        return source_file

    def load(self) -> types.ModuleType:
        """Import the represented Python module."""
        return importlib.import_module(self.location)


class TypeAnnotation:
    """Format Python type annotations for display."""

    @staticmethod
    def name(annotation: object) -> str:
        """Return a readable name for a type annotation."""
        if annotation is None or annotation is type(None):
            return "None"

        origin = typing.get_origin(annotation)
        if origin in (typing.Union, types.UnionType):
            return " | ".join(TypeAnnotation.name(arg) for arg in typing.get_args(annotation))

        if origin is not None:
            arguments = ", ".join(TypeAnnotation.name(arg) for arg in typing.get_args(annotation))
            return (
                f"{TypeAnnotation.name(origin)}[{arguments}]"
                if arguments
                else TypeAnnotation.name(origin)
            )

        return getattr(annotation, "__name__", str(annotation))


@dataclasses.dataclass
class Signature:
    """Annotated input and output types of a Python function."""

    args: dict[str, str] = dataclasses.field(default_factory=dict)
    returns: str | None = None

    @classmethod
    def read(cls, function: Function) -> Signature:
        """Read the annotated argument and return types of a function."""
        signature = inspect.signature(function.load(), eval_str=True)
        return cls(
            args={
                name: TypeAnnotation.name(parameter.annotation)
                for name, parameter in signature.parameters.items()
                if parameter.annotation is not inspect.Parameter.empty
            },
            returns=(
                TypeAnnotation.name(signature.return_annotation)
                if signature.return_annotation is not inspect.Signature.empty
                else None
            ),
        )


@dataclasses.dataclass(frozen=True)
class Function:
    """Represent a named callable in a Python module."""

    module: Module
    name: str

    @classmethod
    def from_callable(cls, function: object) -> Function:
        """Create a function reference from a callable's module and qualified name."""
        if not callable(function):
            raise TypeError("function must be a Python callable")

        module_path = getattr(function, "__module__", None)
        function_name = getattr(function, "__qualname__", None)
        if not isinstance(module_path, str) or not isinstance(function_name, str):
            raise ValueError(
                "Callable must have a module and function name; pass an entrypoint string instead"
            )
        if not Module.is_valid_location(module_path):
            raise ValueError("Function reference module must be an importable dotted module name")
        if not _is_valid_qualified_name(function_name):
            raise ValueError("Function reference name must be a Python qualified name")

        return cls(Module(module_path), function_name)

    @functools.cached_property
    def signature(self) -> Signature:
        """Return the annotated signature of this function."""
        return Signature.read(self)

    def load(self) -> typing.Callable[..., typing.Any]:
        """Import the callable from its module."""
        entrypoint = Entrypoint(Entrypoint.format(self.module.location, self.name))
        function = entrypoint.resolve()
        if not callable(function):
            raise TypeError(f"{self.name} in module {self.module.location} is not callable")
        return typing.cast(typing.Callable[..., typing.Any], function)


class Entrypoint:
    """Parse and expose the module and function addressed by an entrypoint."""

    def __init__(self, entrypoint: str, package: PackageProvenance | None = None) -> None:
        """Create an entrypoint with optional package provenance from a saved build."""
        module_path, function_name = self._split_entrypoint(entrypoint)
        self._validate_module_path(module_path)
        self._validate_function_entrypoint(entrypoint, function_name)

        self._module_path = module_path
        self._function_name = function_name
        self.package = package

    @classmethod
    def from_path(
        cls, path: pathlib.Path, import_root: pathlib.Path, function_name: str
    ) -> Entrypoint:
        """Create an entrypoint for a Python file beneath an import root.

        Args:
            path: Python source file to address.
            import_root: Directory from which the file is importable.
            function_name: Function or attribute name in the module.

        Returns:
            An entrypoint using the file's dotted module path.
        """
        module_path = ".".join(path.resolve().relative_to(import_root).with_suffix("").parts)
        return cls(cls.format(module_path, function_name))

    @classmethod
    def format(cls, module_path: str, function_name: str) -> str:
        """Format validated module and function names as an entrypoint."""
        entrypoint = f"{module_path}:{function_name}"
        cls._validate_module_path(module_path)
        cls._validate_function_entrypoint(entrypoint, function_name)
        return entrypoint

    def resolve(self) -> object:
        """Resolve the object named by this entrypoint."""
        resolved: object = self.module.load()
        for name in self._function_name.split("."):
            resolved = getattr(resolved, name)
        return resolved

    def load(self) -> typing.Callable[..., typing.Any]:
        """Load the callable and include package provenance in resolution errors.

        Returns:
            The resolved Python callable, without enforcing a package version.

        Raises:
            ValueError: The module or callable cannot be resolved.
        """
        try:
            function = self.resolve()
            if not callable(function):
                raise TypeError(
                    f"{self._function_name} in module {self._module_path} is not callable"
                )
            return typing.cast(typing.Callable[..., typing.Any], function)
        except (ImportError, AttributeError, TypeError) as error:
            try:
                available = str(self.module.package)
            except (ImportError, ValueError) as package_error:
                available = f"unresolved ({package_error})"
            raise ValueError(
                f"Could not resolve callable {self._module_path}:{self._function_name}: {error}; "
                f"recorded package provenance: {self.package or 'unavailable'}; "
                f"available runtime package: {available}"
            ) from error

    @staticmethod
    def _split_entrypoint(entrypoint: str) -> tuple[str, str]:
        if ":" not in entrypoint:
            raise ValueError(f"Invalid entrypoint: {entrypoint}. Expected 'module.path:qualname'")

        module_path, function_name = entrypoint.rsplit(":", 1)
        return module_path, function_name

    @staticmethod
    def _validate_function_entrypoint(entrypoint: str, function_name: str) -> None:
        if not _is_valid_qualified_name(function_name):
            raise ValueError(f"Invalid function entrypoint: {entrypoint}")

    @staticmethod
    def _validate_module_path(module_path: str) -> None:
        if not Module.is_valid_location(module_path):
            raise ValueError(
                f"Invalid module path in entrypoint {module_path!r}; "
                "use an importable dotted module path"
            )

    @functools.cached_property
    def module(self) -> Module:
        """Return the module component of this entrypoint."""
        return Module(self._module_path)

    @functools.cached_property
    def function(self) -> Function:
        """Return the function component of this entrypoint."""
        return Function(self.module, self._function_name)


__all__ = [
    "Entrypoint",
    "Function",
    "Module",
    "PackageProvenance",
    "Signature",
    "TypeAnnotation",
]
