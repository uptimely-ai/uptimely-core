# `uptimely project`

Build the generated resources for an analytics project.

## `project build`

```console
uptimely project build \
  [--project-root PATH] [--entrypoint MODULE:ATTRIBUTE | --spec PATH] \
  [--features FEATURE [FEATURE ...]]
```

The command validates the complete source specification, compiles one execution
plan, and builds a complete Explorer website. It publishes all four artifacts
as one active bundle:

```text
_generated/build/
├── build.json
├── spec.json
├── execution_plan.json
└── explorer/
    ├── index.html
    └── ... website assets and pages
```

The spec export always contains the complete model. If `--features` is
provided, the plan includes the selected outputs, their dependencies, and the
associated dataset sinks; the Explorer renders that exact plan alongside the
complete spec model. Omit `--features` to compile all features.
Selections must be nonempty and valid. Duplicate names are normalized.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--project-root PATH` | No | Current working directory | Root for source discovery, importing project functions, and generated output paths. |
| `--entrypoint MODULE:ATTRIBUTE` | No | Discover standard sources | Select a Python attribute containing a `PythonSpec` instance. Mutually exclusive with `--spec`. |
| `--spec PATH` | No | Discover standard sources | Select source spec JSON. Mutually exclusive with `--entrypoint`. Relative to the current working directory. |
| `--features FEATURE ...` | No | All features | Select one or more output features and their required dependencies. |

Source discovery checks `config/spec/spec.py` and
`config/spec/spec.json` beneath the project root. If both exist, select one
explicitly with `--entrypoint` or `--spec`.

```console
uptimely project build --project-root examples/pump_analytics
uptimely project build --project-root examples/pump_analytics --features pump_health_score
```

Building may import Python declarations and inspect function signatures, but it
does not execute workflow functions or sinks. Python module-level code still
runs when a declaration or function module is imported; build only trusted
project sources. A successful full or scoped build replaces the previous
active bundle. Source edits do not change an existing build; rebuild explicitly
to publish updated artifacts. If building fails, the last successful bundle
remains active.

`uptimely engine run` executes the saved plan, including configured write
sinks, which may have external side effects. It never compiles or regenerates
artifacts. Missing or invalid builds fail with an actionable command to build
the project.

Artifacts are generated in a sibling staging directory, validated, then
published in place of the previous bundle. A generation failure leaves the
previous active bundle untouched. Builders coordinate through a project lock;
a build fails rather than publishing while another builder or cooperating
consumer holds the bundle lock. Publication uses rollback if replacing the
directory fails; it does not claim a filesystem-wide atomic directory swap.
