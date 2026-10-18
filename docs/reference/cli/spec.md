# `uptimely spec`

Build spec JSON from Python declarations or JSON sources, or inspect
feature dependencies in a spec document.

## `spec build`

```console
uptimely spec build [--entrypoint MODULE:ATTRIBUTE | --spec PATH] [--project-root PATH] [--output PATH]
```

Without an explicit source, the command discovers
`config/spec/spec.py` or `config/spec/spec.json` beneath the
project root (the current directory by default). If both exist, select one
explicitly with `--entrypoint` or `--spec`; neither takes precedence.

Discovered Python modules must expose a `python_spec` value of type
`PythonSpec`. Use `--entrypoint my_project.spec:definition` to select a
different module or attribute. The selected attribute must be a `PythonSpec`
instance, not a factory function; it is not called.
Discovered Python sources are imported with their package
context, preserving relative imports. Enclosing regular packages (directories
with `__init__.py`) are included in the module name. JSON sources are loaded
and validated before writing the generated document. Building does not execute
the analytics workflow, but importing Python declarations executes module-level code.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--entrypoint MODULE:ATTRIBUTE` | No | Discover the standard source | Import path and attribute containing a `PythonSpec` instance. Mutually exclusive with `--spec`. |
| `--spec PATH` | No | Discover the standard source | Source spec JSON path. Mutually exclusive with `--entrypoint`. |
| `--project-root PATH` | No | Current working directory | Add this directory to Python's import path and use it as the base for the default output path. |
| `--output PATH` | No | `_generated/spec/spec.json` under `--project-root` or the current working directory | Destination JSON path. |

Example:

```console
uptimely spec build --project-root examples/pump_analytics
```

Explicit Python source and output:

```console
uptimely spec build \
  --entrypoint examples.pump_analytics.config.spec.spec:python_spec \
  --project-root . \
  --output examples/pump_analytics/_generated/spec/spec.json
```

Explicit `--spec` and `--output` paths are relative to the current working
directory, not `--project-root`. The command does not change working directories.

## `spec feature-graph`

```console
uptimely spec feature-graph [--spec PATH] [--project-root PATH] [--features NAME ...] [--verbose]
```

Prints the number of features in the graph. When selected features are given,
also prints the size of their dependency subset. `--verbose` prints the graph
and selected subset as trees.

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--spec PATH` | No | `_generated/spec/spec.json` under the project root or current working directory | Spec JSON input. |
| `--project-root PATH` | No | Current working directory | Root for resolving defaults and importing function entrypoints. |
| `--features NAME ...` | No | All features | Select output features and their dependencies. |
| `--verbose` | No | `false` | Print graph details when enabled. |
