# Uptimely config

## Selecting a configuration

### Named configs

Place default settings in `uptimely.toml` at the project root. Named
environment configs live in `config/<name>.toml`. Uptimely loads and validates
the default settings at construction, then applies the selected config as a
recursive override. For example, `uptimely run --config prod` loads
`config/prod.toml` and replaces only the values it defines. Use
`Uptimely(config="prod")` for the same behavior in Python.

### Explicit TOML files

The Uptimely CLI and MCP server also accept an explicit TOML file with
`--config PATH`, and the Python API accepts it as `config_path=PATH`. Explicit
relative paths resolve from the current working directory. An explicit file
is loaded on its own and does not merge with `uptimely.toml`.

### Loading and validation

If the default file is absent, Uptimely uses defaults. An explicit config file
must exist. Invalid configuration is reported when Uptimely is constructed,
including for builds. Construct a new Uptimely instance to read file changes.
CLI runs construct a fresh instance, while the MCP server retains its
configuration until it is restarted.

## Configuration sections

The Spec defines the workflow. The Engine receives runtime settings separately,
so paths and parameters can change between runs without changing the compiled
plan. The file has three top-level sections:

```toml
[engine.backend]
type = "python_venv"
dataframe = "polars"
evaluation = "eager"

[paths]
input = "data/input/source.csv"
output = "data/output/results.csv"

[params]
threshold = 10
```

| Section | Purpose |
| --- | --- |
| `engine` | Backend settings for the Engine. |
| `paths` | Project-relative or absolute file and directory locations referenced by `$paths.<name>`. |
| `params` | Scalar values referenced by `$params.<name>`. |

### Paths and parameters

Relative paths resolve against the project root. Absolute paths are preserved.
Parameter values pass through to functions unchanged. Missing values for
required parameters fail when the corresponding function is invoked.

## Backend settings

The `engine` section contains backend settings:

| Setting | Purpose |
| --- | --- |
| `engine.backend.type` | Names the configured engine environment. |
| `engine.backend.definition` | Optional path to engine-specific configuration. |
| `engine.backend.dataframe` | Selects the dataframe backend. The built-in Engine supports `polars`. |
| `engine.backend.evaluation` | Reserved setting. It does not currently change evaluation behavior. |
| `engine.backend.batch_size` | Reserved setting. It does not currently change data access or batching. |

The backend must be compatible with the saved execution plan. An incompatible
configuration causes execution to fail rather than changing how the plan is
interpreted. Backend compatibility and configuration checks run regardless of
runtime validation mode.
