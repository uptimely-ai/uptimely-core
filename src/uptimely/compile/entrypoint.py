"""Load Python function entrypoints and read their annotated signatures."""

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

from uptimely.analytics import storage

REMOTE_SCHEMES = {"https", "s3"}
REMOTE_READ_TIMEOUT = 30


class _RemoteModuleLoader(abc.SourceLoader):
    """Load one Python source file from a supported remote location."""

    def __init__(self, location: str) -> None:
        self.location = location

    def get_filename(self, fullname: str) -> str:
        return self.location

    def get_data(self, path: str) -> bytes:
        if parse.urlsplit(self.location).scheme == "s3":
            return storage.Storage.read(self.location).encode("utf-8")
        with request.urlopen(self.location, timeout=REMOTE_READ_TIMEOUT) as response:
            if parse.urlsplit(response.geturl()).scheme != "https":
                raise ValueError("HTTPS function references must not redirect to another scheme")
            return response.read()


def _load_module(location: str, loader: abc.Loader | None = None) -> types.ModuleType:
    """Load a file or remote module once, removing failed imports from the cache."""
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


@dataclasses.dataclass
class FunctionSignature:
    """Annotated input and output types of a Python function."""

    args: dict[str, str] = dataclasses.field(default_factory=dict)
    returns: str | None = None


def load_callable(entrypoint: str, root: pathlib.Path | None = None) -> typing.Callable:
    """Import the callable addressed by an entrypoint.

    Args:
        entrypoint: An import path, local Python file, HTTPS URL, or S3 URI
            followed by ``:function``. Only load code from trusted sources.
        root: Directory added to ``sys.path`` so the module becomes importable.

    Returns:
        The imported callable.

    Raises:
        ValueError: If the entrypoint is invalid or uses an unsupported scheme.
        ImportError: If the module cannot be imported.
        AttributeError: If the module has no such function.
        TypeError: If the referenced attribute is not callable.
    """
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
    if root is not None and str(root) not in sys.path:
        sys.path.insert(0, str(root))

    path = pathlib.Path(module_path)
    if scheme in REMOTE_SCHEMES:
        location = parse.urlsplit(module_path)
        if not location.netloc or not location.path.strip("/"):
            raise ValueError(f"Function reference must point to a source file: {module_path}")
        module = _load_module(module_path, _RemoteModuleLoader(module_path))
    elif path.is_absolute() or module_path.startswith(("./", "../")):
        path = path if path.is_absolute() else (root or pathlib.Path.cwd()) / path
        path = path.resolve()
        module = _load_module(str(path))
    else:
        if module_path.endswith(".py"):
            module_path = module_path[:-3]
        module_path = module_path.replace("/", ".")
        module = importlib.import_module(module_path)
    if not hasattr(module, function_name):
        raise AttributeError(f"Function {function_name} not found in module {module_path}")

    function = getattr(module, function_name)
    if not callable(function):
        raise TypeError(f"{function_name} in module {module_path} is not callable")
    return function


def read_signature(entrypoint: str, root: pathlib.Path | None = None) -> FunctionSignature:
    """Read the annotated argument and return types of an entrypoint.

    Args:
        entrypoint: An import path, local file, HTTPS URL, or S3 URI followed
            by ``:function``. Reading signatures imports and executes the module.
        root: Directory added to ``sys.path`` so the module becomes importable.

    Returns:
        The annotated signature; unannotated parameters are omitted.
    """
    func = load_callable(entrypoint, root)
    hints = typing.get_type_hints(func)
    parameters = inspect.signature(func).parameters

    return FunctionSignature(
        args={name: type_name(hints[name]) for name in parameters if name in hints},
        returns=type_name(hints["return"]) if "return" in hints else None,
    )


def type_name(annotation: object) -> str:
    """Return a readable name for a type annotation."""
    if annotation is None or annotation is type(None):
        return "None"

    if isinstance(annotation, (types.UnionType, type(int | str))):
        return " | ".join(type_name(arg) for arg in typing.get_args(annotation))

    origin = typing.get_origin(annotation)
    if origin is not None:
        arguments = ", ".join(type_name(arg) for arg in typing.get_args(annotation))
        return f"{type_name(origin)}[{arguments}]" if arguments else type_name(origin)

    return getattr(annotation, "__name__", str(annotation))
