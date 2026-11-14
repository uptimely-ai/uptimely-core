# Uptimely config

Place `uptimely.toml` at the project root. The Engine reads its runtime
configuration from this file by default. Use `uptimely run --config PATH` or the
MCP server's `--config PATH` option to load a different TOML file instead.

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
