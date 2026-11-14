# Folder structure

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
│   └── project_functions/
│       ├── __init__.py
│       ├── analytics.py
│       ├── io.py
│       └── merge.py
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

The included cooling-pump example uses distinctively named Python files
directly under `src/` instead of the package directory shown above. Both
layouts work with project source imports.

## Folder responsibilities

| Path | Responsibility |
| --- | --- |
| `data/input/` | Raw data and reference datasets used by the workflow. |
| `data/output/` | Results you want to keep, share, or reuse. |
| `src/` | Importable Python modules for data access, calculations, and output. |
| `spec/` | The workflow specification, written in Python or JSON. |
| `_generated/` | Generated builds, Explorer snapshots, and metadata, logs, and previews from the latest run. |
| `config/config.json` | Engine settings under `engine`, file locations under `paths`, and scalar runtime values under `params`. |

Put source files consumed by the workflow in `data/input/`. Store results you
want to keep, share, or reuse in `data/output/`. Use `_generated/` for disposable
previews and debugging files. Each run replaces
`_generated/run/`, so it does not retain a history of earlier runs.

Uptimely makes the project root and `src/` importable during builds and runs.
Use `--src-path` to select a different source directory for a build or run.
Use a distinctive module name under the source directory to avoid conflicts
with dependencies and Python's standard library. The `uptimely` name is reserved
for the framework.
Python import state is process-wide. Uptimely serializes its project imports, but
other threads can see the active paths and modules. Use separate processes when
independently importing different projects concurrently.

## Runtime configuration

The spec defines the workflow, while `config/config.json` supplies the settings
for a particular run. Reference project paths with `$paths.<name>` and scalar
parameters with `$params.<name>`. Relative paths resolve against the project
root. Parameters pass through unchanged.

Rebuild after changing operators, bindings, or profile grain. You can usually
change runtime parameters, data locations, and validation options without
rebuilding. These settings may change the results without changing the workflow's
dependency graph.

| Setting | Where it belongs | Rebuild required? |
| --- | --- | --- |
| Operators, bindings, and profile grain | `spec/` | Yes |
| Paths, runtime parameters, and validation options | Runtime configuration or run options | Usually no |

The runtime backend must be compatible with the saved execution plan.
An incompatible configuration causes execution to fail rather than changing
how the plan is interpreted.

Merge bindings are also part of the spec. Uptimely uses the built-in default
when no binding is provided, or your chosen implementation when one is declared.

## Organizing analytics projects

### Centralized

Keep the organization's full analytical system in a single project and
repository. This is simple to start with and keeps analytics easy to find and
access. It can scale far, but may eventually need to be split into multiple
projects.

### Clustered

Keep multiple independent Uptimely workflows in one or more repositories.
Each workflow contains its independent spec definition and active build bundle.

Share reusable Python code through packages. Keep each workflow's build bundle
and execution results separate.

### Decentralized

!!! caution
    Automatic composition of spec documents from multiple repositories is not natively
    supported. This pattern requires project-specific assembly tooling.

Each repository owns its analytical code and publishes a versioned JSON spec
partial. A master project combines the fragments into one spec, exposing
cross-repository dependencies through agreed profile and feature identifiers.
Fragments may reference declarations in other fragments. Validate the complete
document after merging and reject conflicting definitions.

Record contributing repositories and artifact versions alongside the assembled
spec, rather than maintaining a hand-edited copy of every team's declarations.
Publishing JSON does not require distributing implementation code, but executing
the combined workflow still requires callable implementations or wrappers.
