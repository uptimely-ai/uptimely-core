"""Address and load importable Python modules and callables."""

from __future__ import annotations

import dataclasses
import functools
import importlib
import inspect
import pathlib
import types
import typing

from . import origin, signatures


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

    def read_package(self) -> origin.PackageOrigin:
        """Read installed package provenance without importing this module.

        Raises:
            ValueError: The package namespace has ambiguous distribution ownership.
        """
        return origin.PackageOrigin.read(self.location)

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


@dataclasses.dataclass(frozen=True)
class Function:
    """Represent a named callable in a Python module."""

    module: Module
    name: str

    @staticmethod
    def _is_valid_qualified_name(name: str) -> bool:
        """Return whether a dotted name contains only Python identifiers."""
        return bool(name.strip()) and all(part.isidentifier() for part in name.split("."))

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
        if not Function._is_valid_qualified_name(function_name):
            raise ValueError("Function reference name must be a Python qualified name")

        return cls(Module(module_path), function_name)

    def read_signature(self) -> signatures.Signature:
        """Import this function and read its annotated signature.

        Raises:
            ImportError: The function's module or a dependency cannot be imported.
            NameError: A signature annotation refers to an unavailable name.
            TypeError: The resolved function has no inspectable signature.
            ValueError: The function's signature or annotations cannot be inspected.
        """
        return signatures.Signature.read(self)

    @functools.cached_property
    def docstring(self) -> str | None:
        """Return the cleaned docstring of this function, importing its module."""
        return inspect.getdoc(self.load())

    def load(self) -> typing.Callable[..., typing.Any]:
        """Import the callable from its module."""
        function: object = self.module.load()
        for name in self.name.split("."):
            function = getattr(function, name)
        if not callable(function):
            raise TypeError(f"{self.name} in module {self.module.location} is not callable")
        return typing.cast(typing.Callable[..., typing.Any], function)


class Entrypoint:
    """Parse and expose the module and function addressed by an entrypoint."""

    def __init__(self, entrypoint: str, package: origin.PackageOrigin | None = None) -> None:
        """Create an entrypoint with optional package provenance from a saved build."""
        module_path, function_name = self._split_entrypoint(entrypoint)
        self._validate_module_path(module_path)
        self._validate_function_entrypoint(entrypoint, function_name)

        self._module_path = module_path
        self._function_name = function_name
        self.package = package

    def read_package(self) -> origin.PackageOrigin:
        """Read package provenance for this entrypoint without importing its module."""
        return self.module.read_package()

    def read_source_origin(self, project_root: pathlib.Path | None) -> origin.SourceOrigin:
        """Identify the callable's implementation as project or installed code.

        Args:
            project_root: Project directory, or None when it is unavailable.

        Returns:
            Verified source origin and, for installed code, the distribution name.
        """
        if project_root is None:
            return origin.SourceOrigin("unknown")
        return origin.read_source_origin(self.function.load(), project_root)

    def read_signature(self) -> signatures.Signature:
        """Import this entrypoint and read its callable signature."""
        return self.function.read_signature()

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
                available = str(self.module.read_package())
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
        if not Function._is_valid_qualified_name(function_name):
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
