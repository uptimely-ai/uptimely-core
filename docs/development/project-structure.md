# Analytics project structure

This page shows a recommended project layout for a single analytics project built with Uptimely Core.

## Suggested structure

A practical setup keeps source data, Python declarations, and generated artifacts
separate. This minimal layout follows the end-to-end example; supporting modules
are omitted:

```text
project/
├── data/
├── functions/
│   ├── source.py
│   └── calculation.py
├── config/
│   ├── engine.json
│   └── spec/
│       ├── spec.py
│       ├── dataset_<name>.py
│       ├── entity.py
│       ├── dimension.py
│       └── functions.py
└── _generated/
    └── build/
        ├── build.json
        ├── spec.json
        ├── execution_plan.json
        └── explorer/
```

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/` | Raw or reference datasets used by the analytics workflow. |
| `functions/` | Reusable source, calculation, and write functions. |
| `config/spec/` | Python declarations that define entities, datasets, and relationships. |
| `_generated/` | Generated project artifacts. The active build is stored in `_generated/build/`. |
| `config/engine.json` | Engine settings and bind values used to resolve runtime placeholders. |

This separation keeps the project easy to reason about: specification declarations
live in config, runtime logic lives in functions, and generated resources stay
clearly separate from source inputs.

## Active build bundle

The active-build contract uses one bundle at `_generated/build/`:

```text
_generated/
└── build/
    ├── build.json
    ├── spec.json
    ├── execution_plan.json
    └── explorer/
        ├── index.html
        └── ... website assets and pages
```

`build.json` records its schema version, the Uptimely version, the selected
features (`null` means all features), relative artifact paths, and the complete
Explorer file inventory. A scoped feature list is nonempty and normalized to
unique, sorted names. The spec artifact always contains the complete model;
the execution plan may be scoped to selected outputs and their dependencies.
The shared loader rejects missing or invalid artifacts and validates the saved
execution plan. A successful build replaces the prior active bundle, while a
failed build leaves that bundle intact. Source edits do not trigger a rebuild:
run `uptimely project build` explicitly to publish updates. Engine, Explorer,
feature-graph CLI, and MCP consumers use the saved bundle and fail with an
actionable build command if it is missing or invalid.

Building imports declarations and may inspect function signatures, but never
executes workflow functions or sinks. Engine and MCP execute the saved plan as
is, including configured sinks that may have external side effects. Explorer
serves the saved website without compiling, rendering, or modifying it.

The fixed project structure enables automation of repetitive setup and tooling
while preserving flexibility in the analytics implementation.

The [end-to-end example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/pump_analytics/README.md) uses CLI commands
for project builds, execution, Explorer, and feature graphs.
`uptimely project build --project-root <project>` discovers
`config/spec/spec.py` or `config/spec/spec.json`, validates the source, and
generates a complete active bundle under `_generated/build/`. Use
`--features <name> [<name> ...]` to publish a scoped plan; omit it to include
all features. Python sources expose `python_spec`, a `PythonSpec` instance. Use
`--entrypoint
<module>:<attribute>` or `--spec <path>` to select a source explicitly; this
is required when both standard sources exist. The generated website and plan
are included in that bundle. `uptimely spec feature-graph` prints graph
summaries and, with `--verbose`, dependency trees from the saved spec without
writing files. Engine and Explorer do not regenerate from source; edits require
an explicit rebuild. See the [CLI reference](../reference/cli.md) for recovery
behavior and the documented commands.
The [smaller Python example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/simple_analytics/README.md) demonstrates
spec declarations independently of the full compilation and execution workflow.
