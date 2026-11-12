# Python entrypoints

An entrypoint identifies a function with `"module.path:function_name"`.
Install the function's package in both the build and runtime environments.
Uptimely checks the function signature during compilation and loads the function
when the engine runs.

```python
from uptimely.entrypoint import Entrypoint

function = Entrypoint("my_package.calculations:calculate").load()
```

Loading an entrypoint imports and runs the referenced module. Only load code
you trust. Use `PackageProvenance` to inspect installed package information
without importing the function module.

::: uptimely.entrypoint
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - Entrypoint
        - Function
        - Module
        - Signature
        - TypeAnnotation
        - PackageProvenance
        - SourceOrigin
