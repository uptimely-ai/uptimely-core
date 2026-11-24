# Project structure {#folder-structure}

An Uptimely Core project brings together data, Python functions, a specification,
and runtime configuration without going into execution details. The layout below keeps these easy to find and
separates them from generated files.

## Suggested structure

```text
project/
├── uptimely.toml
├── pyproject.toml
├── data/
│   ├── input/
│   └── output/
├── requirements/ <-- optional runtime requirements
│   └── pyproject.toml
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
├── tests/
│   └── uptimely/
└── artifacts/
    ├── build/
    │   ├── build.json
    │   ├── spec.json
    │   ├── plan.json
    │   └── explorer.json
    └── run/
        ├── run.json
        ├── log.jsonl
        └── preview/
            └── <profile>.json
```


## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/input/` | Local data and reference datasets used by the workflow. |
| `data/output/` | Results you want to keep, share, or reuse. |
| `src/` | Importable Python modules for data access, calculations, and output. |
| `spec/` | The workflow specification, written in Python or JSON. |
| `tests/uptimely/` | Default folder for project operator cases. |
| `requirements/` | Optional definition of package dependencies and laguage version. The Python runtime uses `requirements/pyproject.toml`. |
| `artifacts/` | Generated builds, Explorer snapshots, and metadata, logs, and previews from the latest run. |
| `uptimely.toml` | Project defaults and settings under `application`, `code`, `engine`, `test`, `paths`, and `params`. See [Configure a project](configuration.md). |
| `pyproject.toml` | Project metadata and dependencies. It supplies Python runtime metadata unless another definition is selected or discovered under `requirements/`. |

## Source code

The build makes the project root and selected source directory available for
importing project code. Set `code.src` in config or use
`--src-path` to select another directory for the build. The build copies the
selected source into the build bundle. Runs always use this bundled copy,
never the source directory in the project root.

Use a distinctive module name under the source directory to avoid conflicts
with dependencies and Python's standard library. The `uptimely` name is reserved
for the framework.

Python import state is process-wide. Uptimely serializes its project imports, but
other threads can see the active paths and modules. Use separate processes when
independently importing different projects concurrently.

## Runtime

Set `code.requirements` to a requirements definition file. When unset, the build
uses `requirements/pyproject.toml` if present or extracts dependencies from the
project root's `pyproject.toml`.

## Spec profiles

Keep a profile in one module while its declarations remain easy to navigate.
For larger profiles, use a package to separate the profile, features, and
related declarations while keeping a `profile.py` entrypoint.

## Files

Put source files consumed by the workflow in `data/input/`. Store results you
want to keep, share, or reuse in `data/output/`. Use `artifacts/` for disposable
previews and debugging files. Each run replaces
`artifacts/run/`, so it does not retain a history of earlier runs.
