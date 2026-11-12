# Projects

`Project` builds and loads project bundles. It uses the current directory by
default; pass a path to work with another project.

```python
from uptimely import Engine, Project

project = Project("path/to/project")
bundle = project.build()
result = Engine(bundle).run()
```

Use `load_build_bundle()` to load a bundle. To keep it protected from changes
while you use it, open it with `read_build_bundle()`:

```python
with project.read_build_bundle() as bundle:
    result = Engine(bundle).run()
```

For lower-level build and bundle operations, see the functions listed below.

::: uptimely.project
    options:
      heading_level: 2
      show_root_heading: false
      members: [Project, build, load_build_bundle, read_build_bundle]
