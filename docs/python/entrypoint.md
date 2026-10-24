# Python entrypoints

`uptimely.entrypoint` loads Python callables and inspects their annotated
signatures. Entry points use `module.path:qualname` syntax and resolve through
Python's import system. The module's package must be installed in the build and
runtime environments; editable installs support local development. Uptimely
does not install packages or add project paths to `sys.path`.

The distribution name and version associated with each entrypoint are recorded
as build provenance. The engine does not enforce that version. If the callable
cannot be resolved or is incompatible, the error includes the recorded package
metadata and the package metadata available at runtime. Ambiguous installed
package namespaces are reported explicitly.

Use `Entrypoint` to access the function and module. Resolve the named object
with `entrypoint.resolve()`, or load it as a callable with
`entrypoint.load()`; callable resolution errors include saved package provenance.
Pass saved provenance to `Entrypoint(location, package=recorded_package)` and
access it through `entrypoint.package`. The engine passes these entrypoint
objects to the callable executor rather than passing package metadata separately.
`entrypoint.function.load()` loads the callable and
preserves the underlying Python exception. Create a `Function` from an existing
callable with `Function.from_callable(callable)`, using its `__module__` and
`__qualname__` without importing the module. Inspect annotations with
`entrypoint.function.signature`. Module and function objects are reused within
an entrypoint, and signatures are read once per `Function` instance. Use
`Entrypoint.from_path(path, import_root, function_name)` to create an entrypoint
from a Python source file's location beneath an import root. Use
`Entrypoint.format(module_path, function_name)` to format validated components
as an entrypoint string.

Read `entrypoint.module.package` for a `PackageProvenance` value without importing
the implementation. Package metadata is read once per `Module` instance.
The value exposes `distribution` and `version`, along with `top_level_package`
and `distribution_candidates`. `PackageProvenance.read(module_path)` also
supports standalone metadata lookup.

The installed-package index is shared across lookups and refreshed when
`sys.path` changes, avoiding a full environment scan for each entrypoint.
After installing or removing distributions in a running process without changing
`sys.path`, call `PackageProvenance.invalidate_cache()` before creating new
module objects or compiling again. Existing `Module` instances retain their
previously read provenance.

Read `entrypoint.module.source_file` to get the loaded module's file path.
Modules without a file raise `ValueError`.

!!! warning "Only load trusted code"

    Loading a callable, reading its signature, and accessing `module.source_file`
    import and execute the referenced Python module if it is not already loaded.

<div class="api-reference" markdown="1">

## entrypoint

::: uptimely.entrypoint
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - Entrypoint
        - Module
        - Function
        - Signature
        - TypeAnnotation
        - PackageProvenance

</div>
