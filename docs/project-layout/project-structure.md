# Analytics project structure

An Uptimely Core project brings together data, Python functions, a specification,
and runtime configuration. The layout below keeps these easy to find and
separates them from generated files.

## Suggested structure

```text
project/
├── data/
│   ├── input/
│   └── output/
├── src/
│   ├── analytics.py
│   ├── io.py
│   └── merge.py
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
| `data/input/` | Raw data and reference datasets used by the workflow. |
| `data/output/` | Results you want to keep, share, or reuse. |
| `src/` | Importable Python modules for data access, calculations, and output. |
| `spec/` | The workflow specification, written in Python or JSON. |
| `_generated/` | Generated builds, Explorer snapshots, and metadata, logs, and previews from the latest run. |
| `config/config.json` | Engine settings under `engine` and runtime parameter values under `params`. |

Use `_generated/` for disposable previews and debugging files, and `data/output/`
for results that belong to the project's data. Each run replaces
`_generated/run/`, so it does not retain a history of earlier runs.


## Runtime configuration

The spec defines the workflow, while `config/config.json` supplies the settings
for a particular run. Reference parameter values with `$params.<name>`.

Rebuild after changing operators, bindings, or profile grain. You can usually
change runtime parameters, data locations, and validation options without
rebuilding. These settings may change the results without changing the workflow's
dependency graph.

| Setting | Where it belongs | Rebuild required? |
| --- | --- | --- |
| Operators, bindings, and profile grain | `spec/` | Yes |
| Runtime parameters, data locations, and validation options | Runtime configuration or run options | Usually no |

The runtime backend must be compatible with the saved execution plan.
An incompatible configuration causes execution to fail rather than changing
how the plan is interpreted.

Merge bindings are also part of the spec. Uptimely uses the built-in default
when no binding is provided, or your chosen implementation when one is declared.
