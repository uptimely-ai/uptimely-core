# Python entrypoints

An entrypoint identifies a function with `"module.path:function_name"`.
Install the function's package in both the build and runtime environments.
Uptimely inspects function signatures before compilation and loads the function
when the engine runs. Signature inspection is performed by the independent
[Binding inspector](inspector.md), not by the compiler.

```python
from uptimely.codebase.python.entrypoint import Entrypoint

function = Entrypoint("my_package.calculations:calculate").load()
```

Loading an entrypoint imports and runs the referenced module. Only load code
you trust. Use `PackageOrigin` to inspect installed package information
without importing the function module.

::: uptimely.codebase.python.entrypoint
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - Entrypoint
        - Function
        - Module
