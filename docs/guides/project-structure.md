# Project structure {#folder-structure}

An Uptimely Core project brings together data, Python functions, a specification,
and runtime configuration. The layout below keeps these easy to find and
separates them from generated files.

## Suggested structure

```text
project/
├── uptimely.toml
├── data/
│   ├── input/
│   └── output/
├── src/
│   └── project_functions/
│       ├── __init__.py
│       ├── analytics.py
│       ├── io.py
│       └── merge.py
├── spec/
│   ├── spec.py <-- default spec entrypoint
│   ├── profile_<name>.py
│   ├── profile_<name>/
│   │   ├── __init__.py
│   │   ├── profile.py
│   │   └── features.py
│   └── dimension.py
└── artifacts/
    ├── build/
    │   ├── build.json
    │   ├── spec.json
    │   └── plan.json
    ├── explorer.json
    └── run/
        ├── run.json
        ├── log.jsonl
        └── preview/
            └── <profile>.json
```

The included cooling-pump example uses distinctively named Python files
directly under `src/` instead of the package directory shown above. Both
layouts work with project source imports.

Keep a profile in one module while its declarations remain easy to navigate.
For larger profiles, use a package to separate the profile, features, and
related declarations while keeping a `profile.py` entrypoint.

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/input/` | Local data and reference datasets used by the workflow. |
| `data/output/` | Results you want to keep, share, or reuse. |
| `src/` | Importable Python modules for data access, calculations, and output. |
| `spec/` | The workflow specification, written in Python or JSON. |
| `artifacts/` | Generated builds, Explorer snapshots, and metadata, logs, and previews from the latest run. |
| `uptimely.toml` | Project defaults and runtime settings under `application`, `engine`, `paths`, and `params`. See [Configure a project](configuration.md). |

## Files

Put source files consumed by the workflow in `data/input/`. Store results you
want to keep, share, or reuse in `data/output/`. Use `artifacts/` for disposable
previews and debugging files. Each run replaces
`artifacts/run/`, so it does not retain a history of earlier runs.

## Python module imports

Uptimely makes the project root and the selected source directory importable
during builds and runs. Set `application.src_path` in config or use
`--src-path` to select a different directory for a build. The build records
that selection, and later runs reuse it unless they provide a run-time override.

Use a distinctive module name under the source directory to avoid conflicts
with dependencies and Python's standard library. The `uptimely` name is reserved
for the framework.

Python import state is process-wide. Uptimely serializes its project imports, but
other threads can see the active paths and modules. Use separate processes when
independently importing different projects concurrently.
