# Project structure {#folder-structure}

An Uptimely Core project brings together data, Python functions, a specification,
and runtime configuration without going into execution details. The layout below keeps these easy to find and
separates them from generated files.

## Suggested structure

```text
project/
├── uptimely.toml
├── data/
│   ├── input/
│   └── output/
├── requirements/ <-- optional runtime requirements
│   └── pyproject.toml
├── code/
│   ├── .devcontainer/
│   ├── pyproject.toml
│   ├── init.sh
│   └── src/
│       └── project_functions/
│           ├── __init__.py
│           ├── analytics.py
│           ├── io.py
│           └── merge.py
├── spec/
│   ├── index.yaml
│   ├── dimensions.yaml
│   ├── functions.yaml
│   └── profiles/
│       ├── <profile>.yaml
│       └── <profile>/
│           └── features.yaml
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
| `code/` | Python source and its development environment. The folder is optional. |
| `code/src/` | Importable Python modules for data access, calculations, and output. |
| `spec/` | The workflow specification, written in YAML, Python, or JSON. |
| `tests/uptimely/` | Default folder for project operator cases. |
| `requirements/` | Optional definition of package dependencies and laguage version. The Python runtime uses `requirements/pyproject.toml`. |
| `artifacts/` | Generated builds, Explorer snapshots, and metadata, logs, and previews from the latest run. |
| `uptimely.toml` | Project defaults and settings under `application`, `code`, `engine`, `test`, `paths`, and `params`. See [Configure a project](configuration.md). |
| `code/pyproject.toml` | Project metadata and dependencies. Select it with `code.requirements` unless another definition is selected or discovered under `requirements/`. |
| `code/.devcontainer/` | Optional development container configuration for the code workspace. |

`code/` is a source and development area, not a second Uptimely project root.
Keep `uptimely.toml`, `spec/`, and workflow data at the outer project root.
The code environment can be synced independently, while Uptimely reads the
specification and project configuration from that outer root.

## Source code

The build makes the project root and selected source directory available for
importing project code. Set `code.src` in config or use
`--src-path` to select another directory for the build. The build copies the
selected source into the build bundle. Runs always use this bundled copy,
never the source directory in the project root.

Paths in `uptimely.toml` are relative to the project root. For the layout above,
set `code.src = "code/src"` and `code.requirements = "code/pyproject.toml"`.

Use a distinctive module name under the source directory to avoid conflicts
with dependencies and Python's standard library. The `uptimely` name is reserved
for the framework.

Python import state is process-wide. Uptimely serializes its project imports, but
other threads can see the active paths and modules. Use separate processes when
independently importing different projects concurrently.

## Runtime

Set `code.requirements` to a requirements definition file. When unset, the build
uses `requirements/pyproject.toml` if present or extracts dependencies from the
project root's `pyproject.toml`. A `pyproject.toml` in another location, such as
`code/pyproject.toml`, must be selected with `code.requirements`.

## Spec profiles

Keep a profile in one file while its declarations remain easy to navigate.
For larger profiles, use a directory to separate features and other fields.
See [YAML authoring](yaml-authoring.md) for composition rules. Python and JSON
specifications are also supported.

## Files

Put source files consumed by the workflow in `data/input/`. Store results you
want to keep, share, or reuse in `data/output/`. Use `artifacts/` for disposable
previews and debugging files. Each run replaces
`artifacts/run/`, so it does not retain a history of earlier runs.
