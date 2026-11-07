# Analytics project structure

This page shows a recommended project layout for a single analytics project built with Uptimely Core.

## Suggested structure

A practical setup keeps source data, spec declarations, runtime configuration
and generated artifacts separate:

```text
project/
├── data/
│   ├── input/
│   └── output/
├── functions/
│   └── analytics.py
├── config/
│   └── config.json
├── spec/
│   ├── spec.py <-- default spec entrypoint
│   ├── profile_<name>.py
│   └── dimension.py
└── _generated/
    ├── build/
    │   ├── build.json
    │   ├── spec.json
    │   └── execution_plan.json
    ├── explorer.json
    └── run/
        ├── run.json
        ├── log.jsonl
        └── preview/
            └── <profile>.json
```

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/input/` | Raw or reference datasets used by the analytics workflow. |
| `data/output/` | Optional durable or intentionally shared results; use these when outputs are part of the project's data. |
| `functions/` | Reusable source, calculation, and write functions. |
| `spec/` | The project specification: either Python declarations or a JSON document. |
| `_generated/` | Disposable generated artifacts. The active build is stored in `_generated/build/`, the current Explorer data snapshot in `_generated/explorer.json`, and the latest run's metadata, logs, and profile previews under `_generated/run/`. Each run replaces that entire directory; no history is retained. |
| `config/config.json` | Runtime engine settings under `engine` and scalar values under `params`, referenced by `$params.<name>`. Kept outside `spec/`. |

This separation keeps the project easy to reason about: specification declarations
live in `spec/`, runtime logic lives in functions, curated data stays under
`data/`, and generated resources stay clearly separate. Keep results under
`_generated/` when they are disposable previews or debugging artifacts; use
`data/output/` when results should be retained, shared, or reused as project data.

Python profile modules subclass `uptimely.spec.python.Profile` and declare
`Operator` objects in `assembly`, optionally grouped by purpose in a mapping.
Profile grain references infer the dimensions and resolutions used by the spec.
Each operator points directly to an implementation in `functions/`, binds its
arguments, and defines its output features. See
[Python authoring](../python/python.md) for the declaration syntax.

## Build-time workflow and runtime configuration

Keep workflow declarations in `spec/` and runtime configuration in
`config/config.json`. Operators, bindings, and profile grain are build-time
settings; changing them requires rebuilding. Runtime parameters, source/sink
locations, and validation controls are supplied at runtime and normally do not
change the graph. Runtime parameters can change results without changing that
graph.

| Setting | Ownership | Rebuild required? |
| --- | --- | --- |
| Operators, bindings, and profile grain | Build-time workflow definition in `spec/` | Yes |
| Runtime parameters, source/sink locations, and validation controls | Project/runtime configuration or run options | Normally no |

The saved plan records its required backend. Runtime configuration cannot
reinterpret it for an incompatible backend; execution fails explicitly. Merge
bindings are build-time declarations: an omitted binding resolves to the
builtin default, and an explicit binding overrides it.

## Building the project

`uptimely build <project>` reads `spec/spec.py` or `spec/spec.json` and generates
the build bundle shown above. If both sources exist, select one with
`--python-spec` or `--json-spec`. Rebuild after source changes: execution and
Explorer use the saved bundle rather than regenerating it.

See the [CLI reference](../cli/index.md) for build options and the
[pump analytics example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/pump_analytics)
for a runnable project. For structures spanning multiple projects or repositories, see
[organizing analytics projects](organize.md).
