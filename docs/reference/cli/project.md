# `uptimely project`

Build the generated resources for an analytics project.

## `project build`

```console
uptimely project build \
  [--project-root PATH] [--python-spec MODULE:ATTRIBUTE | --json-spec PATH] \
  [--features FEATURE [FEATURE ...]] [--verbose]
```

The command validates the complete source specification, compiles one execution
plan, and builds a complete Explorer website. It publishes all four artifacts
as one active bundle:

### Build output

```text
_generated/build/
├── build.json
├── spec.json
├── execution_plan.json
└── explorer/
    ├── index.html
    └── ... website assets and pages
```

### Feature selection

The spec export always contains the complete model. If `--features` is
provided, the plan includes the selected outputs, their dependencies, and the
associated dataset sinks; the Explorer renders that exact plan alongside the
complete spec model. Omit `--features` to compile all features.
Selections must be nonempty and valid. Duplicate names are normalized.

### Options

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Root for source discovery, importing project functions, and generated output paths. |
| `--python-spec MODULE:ATTRIBUTE` | No | Discover standard sources | Select a Python attribute containing a `PythonSpec` instance. Mutually exclusive with `--json-spec`. |
| `--json-spec PATH` | No | Discover standard sources | Select source spec JSON. Mutually exclusive with `--python-spec`. Relative to the current working directory. |
| `--features FEATURE ...` | No | All features | Select one or more output features and their required dependencies. |
| `--verbose` | No | Disabled | Log build duration, output folder, source file, resource counts, and plan size. |

### Build logging

By default, a successful build logs only `Build files created to {path}`.
Warnings and errors remain visible. Add `--verbose` for a summary grouped into:

- **Build:** duration in seconds, output folder, and feature scope.
- **Spec:** source file and numbers of functions, datasets, and features.
- **Plan:** numbers of execution stages and callables.

Duration covers building, validating, and publishing the bundle, not workflow
execution. Spec counts cover the complete specification, including for scoped
builds; features are counted per dataset, excluding dimensions. Plan counts
describe the compiled feature scope. The source file is the original JSON or
Python declaration, not the generated spec export.

### Specification source discovery

Without `--python-spec` or `--json-spec`, source discovery checks
`spec/spec.py` and `spec/spec.json` beneath the project root:

- If only `spec/spec.py` exists, it is selected automatically.
- If only `spec/spec.json` exists, it is selected automatically.
- If both exist, the build fails as ambiguous. Select one with
  `--python-spec` or `--json-spec`.
- If neither exists, the build fails and reports the expected paths.

Use `--python-spec` or `--json-spec` to select a source explicitly, including
one outside the standard paths.

### Examples

```console
uptimely project build --project-root examples/pump_analytics
uptimely project build --project-root examples/pump_analytics --verbose
uptimely project build --project-root examples/pump_analytics --features pump_health_score
```

### Build behavior

Building may import Python declarations and inspect function signatures, but it
does not execute workflow functions or sinks. Python module-level code still
runs when a declaration or function module is imported; build only trusted
project sources. A successful full or scoped build replaces the previous
active bundle. Source edits do not change an existing build; rebuild explicitly
to publish updated artifacts. If building fails, the last successful bundle
remains active.


### Publication and locking

Artifacts are generated in a sibling staging directory, validated, then
published in place of the previous bundle. A generation failure leaves the
previous active bundle untouched. Builders coordinate through a project lock;
a build fails rather than publishing while another builder or cooperating
consumer holds the bundle lock. Publication uses rollback if replacing the
directory fails; it does not claim a filesystem-wide atomic directory swap.
