# Projects

`Uptimely` builds and runs a project. It uses the current directory by
default. Pass a path to work with another project.

```python
from uptimely import Uptimely

app = Uptimely("path/to/project")
app.build()
result = app.run()
```

`run()` executes the saved build without rebuilding it and holds a reader lock
for the duration of execution. It returns an execution result with any invocation
failures in `result.failures`. Pass `validate=True` to check runtime contracts,
or `operator=(profile_id, operator_id)` to run a selected operator and its
prerequisites.

Use `load_build_bundle()` to load a bundle. To keep it protected from changes
while you use it, open it with `read_build_bundle()`:

```python
with app.read_build_bundle() as bundle:
    result = app.create_engine(bundle).run()
```

`Uptimely` loads and validates `uptimely.toml` when it is constructed. Pass
`config_path` to use another TOML file. Explicit relative paths are resolved
from the current working directory. If the default file is absent, configuration
uses defaults. An explicitly requested file must exist. Construct a new `Uptimely`
to pick up changes to the file.

`create_engine()` passes the project's engine settings, paths, and parameters
to the Engine. It rejects bundles from a different project.

For lower-level build and bundle operations, see the functions listed below.

::: uptimely.project
    options:
      heading_level: 2
      show_root_heading: false
      members: [Uptimely, build, load_build_bundle, read_build_bundle]

::: uptimely.project.config
    options:
      heading_level: 2
      show_root_heading: false
      members: [ProjectConfig, Params, Paths]
