# Projects

`Project` stores a resolved project root and builds or reads validated active
build bundles. Import it from `uptimely` or `uptimely.project`.

```python
from uptimely import Engine, Project

project = Project()  # Current directory, resolved when the object is created.
bundle = project.build()
result = Engine(bundle).run()
```

Pass a path to `Project("path/to/project")` to work with another directory.
Construction does not load or build anything. Each build or load returns a fresh
bundle rather than caching the latest build on the project object.

`project.read_build_bundle()` holds a reader lock for the duration of its
context. Use `project.load_build_bundle()` when a lock is not needed after
loading. The existing module-level build and bundle-loading functions remain
available.

Builds validate Spec semantics once during compilation. Explorer rendering and
staged and published bundle loading reuse that validation. Artifact, structural,
and execution-plan checks still run.
The source Spec remains authoritative for function contracts, binding roles,
and optional categories. Rebuild after changing declarations to regenerate the
portable plan and Explorer presentation snapshot.

Standalone `load_build_bundle` and `read_build_bundle` validate Spec semantics by
default. Pass `validate=False` only when the saved Spec has already been
validated and has not changed; all other bundle checks remain enabled.

`project.resolve_path(path, default)` preserves an explicit path unchanged,
including relative paths. If `path` is `None`, it joins `default` to the root
stored by `Project`. The module-level `resolve_path` function has been removed.

Project path constants are defined in `uptimely.project.paths` and exported by
`uptimely.project`. Import them from `uptimely.project.paths`. The former
`uptimely.project_paths` forwarding module has been removed.

Portable execution-plan models and serialization live in `uptimely.plan`. The
former `uptimely.execution_plan` forwarding package has been removed; update
imports to `uptimely.plan`.

::: uptimely.project
    options:
      heading_level: 2
      show_root_heading: false
      members:
        - Project
        - build
        - load_build_bundle
        - read_build_bundle
        - load_spec_source
