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
    ├── build/
    │   ├── build.json
    │   ├── spec.json
    │   ├── execution_plan.json
    │   └── explorer/
    ├── spec/                 Standalone spec output during migration
    ├── compile/              Standalone plan output during migration
    └── explorer/             Standalone Explorer output during migration
```

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/` | Raw or reference datasets used by the analytics workflow. |
| `functions/` | Reusable source, calculation, and write functions. |
| `config/spec/` | Python declarations that define entities, datasets, and relationships. |
| `_generated/` | Output created by the tooling, such as exported specification JSON, compiled plans, graphs, and documentation. |
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
unique, sorted names. The shared loader rejects missing or invalid artifacts and validates the saved
execution plan. `uptimely project build` produces this complete bundle. The
shared loader validates under a reader lock; its `read_build_bundle` context
holds that lock for consumers such as a serving process. Builders fail fast
while a cooperating consumer holds the bundle lock. The Engine and Explorer
consumer commands are migrating separately and do not yet consume it.

The fixed project structure enables automation of repetitive setup and tooling
while preserving flexibility in the analytics implementation.

The [end-to-end example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/pump_analytics/README.md) uses CLI commands
for project builds, execution, documentation, and feature graphs.
`uptimely project build --project-root <project>` discovers
`config/spec/spec.py` or `config/spec/spec.json`, validates the source, and
generates the complete active bundle under `_generated/build/`. Python sources
expose `python_spec`, a `PythonSpec` instance. Use `--entrypoint
<module>:<attribute>` or `--spec <path>` to select a source explicitly; this
is required when both standard sources exist. The generated website and plan
are included in that bundle. `uptimely spec feature-graph` prints graph
summaries and, with `--verbose`, dependency trees without writing files.
The [smaller Python example](https://github.com/uptimely-ai/uptimely-core/blob/main/examples/simple_analytics/README.md) demonstrates
spec declarations independently of the full compilation and execution workflow.
