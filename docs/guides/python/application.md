# Build and run in Python {#app}

`Uptimely` builds and runs a project. It uses the current directory by
default. Pass a path to work with another project.

```python
from uptimely import Uptimely

app = Uptimely("path/to/project")
app.build()
result = app.run()
```

For execution options and saved-run access, see [Execute in Python](execution.md).
The [Execution results reference](../../reference/python/engine/results.md)
describes the returned fields and failures.

Use `load_build_bundle()` to load a bundle. To keep it protected from changes
while you use it, open it with `read_build_bundle()`:

```python
with app.read_build_bundle() as bundle:
    result = app.create_engine(bundle).run()
```

See [Configure a project](../configuration.md#selecting-a-configuration)
for named configs, explicit files, and configuration lifetime.
The [configuration reference](../../reference/configuration.md#application-settings)
describes project defaults, and
[Build a project](../build.md#specification-source-discovery) covers source discovery.

`create_engine()` passes the project's engine settings, paths, parameters, and
run defaults to the Engine. It rejects bundles from a different project.

See [Builds and bundles](../../reference/python/build.md) for lower-level operations
and the [Application API](../../reference/python/application.md) for method details.
