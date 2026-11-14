# Projects

`Project` builds and loads project bundles. It uses the current directory by
default; pass a path to work with another project.

```python
from uptimely import Project

project = Project("path/to/project")
bundle = project.build()
result = project.create_engine(bundle).run()
```

Use `load_build_bundle()` to load a bundle. To keep it protected from changes
while you use it, open it with `read_build_bundle()`:

```python
with project.read_build_bundle() as bundle:
    result = project.create_engine(bundle).run()
```

`Project` loads and validates `uptimely.toml` when it is constructed. Pass
`config_path` to use another TOML file. Explicit relative paths are resolved
from the current working directory. If the default file is absent, configuration
uses defaults. An explicitly requested file must exist. Construct a new `Project`
to pick up changes to the file.

`create_engine()` passes the project's engine settings, paths, and parameters
to the Engine. It rejects bundles from a different project.

For lower-level build and bundle operations, see the functions listed below.

::: uptimely.project
    options:
      heading_level: 2
      show_root_heading: false
      members: [Project, build, load_build_bundle, read_build_bundle]

::: uptimely.project.config
    options:
      heading_level: 2
      show_root_heading: false
      members: [ProjectConfig, Params, Paths]
