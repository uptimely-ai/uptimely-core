"""Load Python function entrypoints and read their annotated signatures."""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import inspect
import pathlib
import sys
import types
import typing
from importlib import abc, util
from urllib import parse, request

from uptimely import storage as storage_module

REMOTE_SCHEMES = {"https", "s3"}
REMOTE_READ_TIMEOUT = 30


class _RemoteModuleLoader(abc.SourceLoader):
    """Load one Python source file from a supported remote location."""

    def __init__(self, location: str) -> None:
        self.location = location

    def get_filename(self, _fullname: str) -> str:
        return self.location

    def get_data(self, _path: str) -> bytes:
        if parse.urlsplit(self.location).scheme == "s3":
            return storage_module.Storage.read(self.location).encode("utf-8")
        with request.urlopen(self.location, timeout=REMOTE_READ_TIMEOUT) as response:
            if parse.urlsplit(response.geturl()).scheme != "https":
                raise ValueError("HTTPS function references must not redirect to another scheme")
            return response.read()


class Module:
    """Represent and load a Python module from a file, import path, or URL."""

    def __init__(self, location: str, root: pathlib.Path | None = None) -> None:
        self.location = location
        self.root = root

    @property
    def source_file(self) -> str:
        """Return the loaded module's file path or remote source URI.

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
        if self.root is not None and str(self.root) not in sys.path:
            sys.path.insert(0, str(self.root))

        scheme = parse.urlsplit(self.location).scheme
        if scheme in REMOTE_SCHEMES:
            return self.load_external()

        path = pathlib.Path(self.location)
        if path.is_absolute() or self.location.startswith(("./", "../")):
            path = path if path.is_absolute() else (self.root or pathlib.Path.cwd()) / path
            return self._load_module(str(path.resolve()))

        module_path = self.location[:-3] if self.location.endswith(".py") else self.location
        return importlib.import_module(module_path.replace("/", "."))

    def load_external(self) -> types.ModuleType:
        """Load the represented source file from HTTPS or S3."""
        location = parse.urlsplit(self.location)
        if location.scheme not in REMOTE_SCHEMES:
            raise ValueError(f"Unsupported external module scheme: {location.scheme}")
        if not location.netloc or not location.path.strip("/"):
            raise ValueError(f"Function reference must point to a source file: {self.location}")
        return self._load_module(self.location, _RemoteModuleLoader(self.location))

    @staticmethod
    def _load_module(location: str, loader: abc.Loader | None = None) -> types.ModuleType:
        """Load a module once, removing failed imports from the cache."""
        module_name = f"_uptimely_function_{hashlib.sha256(location.encode()).hexdigest()}"
        if module_name in sys.modules:
            return sys.modules[module_name]
        module_spec = (
            util.spec_from_loader(module_name, loader, origin=location)
            if loader is not None
            else util.spec_from_file_location(module_name, location)
        )
        if module_spec is None or module_spec.loader is None:
            raise ImportError(f"Cannot load Python module from {location}")
        module = util.module_from_spec(module_spec)
        module.__file__ = location
        sys.modules[module_name] = module
        try:
            module_spec.loader.exec_module(module)
        except BaseException:
            del sys.modules[module_name]
            raise
        return module


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


class Function:
    """Represent a named callable in a Python module."""

    def __init__(self, module: Module, name: str) -> None:
        self.module = module
        self.name = name

    @property
    def signature(self) -> Signature:
        """Return the annotated signature of this function."""
        return Signature.read(self)

    def load(self) -> typing.Callable[..., typing.Any]:
        """Import the callable from its module."""
        module = self.module.load()
        function = getattr(module, self.name)
        if not callable(function):
            raise TypeError(f"{self.name} in module {self.module.location} is not callable")
        return function


class Entrypoint:
    """Parse and expose the module and function addressed by an entrypoint."""

    def __init__(self, entrypoint: str, root: pathlib.Path | None = None) -> None:
        if ":" not in entrypoint:
            raise ValueError(
                f"Invalid entrypoint: {entrypoint}. "
                "Expected 'module.path:function' or 'path/to/module.py:function'"
            )

        module_path, function_name = entrypoint.rsplit(":", 1)
        scheme = parse.urlsplit(module_path).scheme
        if not module_path.strip() or not function_name.isidentifier():
            raise ValueError(f"Invalid function entrypoint: {entrypoint}")
        if (scheme and scheme not in REMOTE_SCHEMES) or module_path.startswith("git@"):
            raise ValueError(
                f"Unsupported function reference scheme: {module_path}. "
                "Use a Python module, local file, https:// URL, or s3:// URI."
            )

        self.root = root
        self._module_path = module_path
        self._function_name = function_name

    @property
    def module(self) -> Module:
        """Return the module component of this entrypoint."""
        return Module(self._module_path, self.root)

    @property
    def function(self) -> Function:
        """Return the function component of this entrypoint."""
        return Function(self.module, self._function_name)


__all__ = [
    "Entrypoint",
    "Function",
    "Module",
    "REMOTE_READ_TIMEOUT",
    "REMOTE_SCHEMES",
    "Signature",
    "TypeAnnotation",
]
