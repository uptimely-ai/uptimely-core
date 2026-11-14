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

## Project settings

The `[project]` section stores defaults for building and running the project:

```toml
[project]
python_spec = "spec.spec:python_spec"
src_path = "src"
```

Set either `python_spec` or `json_spec` to select a specification source, not
both. `python_spec` uses the `MODULE:ATTRIBUTE` entrypoint format. `json_spec`
is a path relative to the project root unless it is absolute. If neither is
set, Uptimely discovers `spec/spec.py` with the `python_spec` attribute or
`spec/spec.json`. Discovery fails if both files exist.

`src_path` is a project-relative or absolute Python source directory. If
omitted, Uptimely uses `src`. CLI values for spec source and source path
override the corresponding settings. A CLI spec source overrides both
configured source fields.

| Setting | Purpose | Default |
| --- | --- | --- |
| `project.python_spec` | Python `MODULE:ATTRIBUTE` entrypoint for the spec. | Discover `spec/spec.py` with the `python_spec` attribute. |
| `project.json_spec` | JSON spec path, relative to the project root or absolute. Mutually exclusive with `python_spec`. | Discover `spec/spec.json`. |
| `project.src_path` | Python source directory, relative to the project root or absolute. | `src` |

Feature selection, runtime validation, build-before-run, and log level remain
command-specific options rather than project settings.

The `[engine]` section includes `preview_rows`, the default maximum number of
rows stored in the run preview. It defaults to `5`. The `--preview ROWS` CLI
option overrides it, while bare `--preview` uses the configured value.

The project root is not configured in `uptimely.toml`. The CLI's positional
project directory or `--project-root` selects it. If neither is given, Uptimely
uses the current working directory. The root is needed to locate the config
file in the first place.

## Configuration sections

The Spec defines the workflow. The Engine receives runtime settings separately,
so paths and parameters can change between runs without changing the compiled
plan. The file has four top-level sections:

```toml
[project]
python_spec = "spec.spec:python_spec"
src_path = "src"

[engine]
preview_rows = 5

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
| `project` | Default specification sources and project execution settings. |
| `engine` | Engine backend settings and the default run preview size. |
| `paths` | Project-relative or absolute file and directory locations referenced by `$paths.<name>`. |
| `params` | Scalar values referenced by `$params.<name>`. |

### Paths and parameters

Relative paths resolve against the project root. Absolute paths are preserved.
Parameter values pass through to functions unchanged. Missing values for
required parameters fail when the corresponding function is invoked.

## Engine settings

The `engine` section contains runtime settings. `preview_rows` controls the
default saved run preview size. Backend settings are nested under
`engine.backend`:

| Setting | Purpose |
| --- | --- |
| `engine.backend.type` | Names the configured engine environment. |
| `engine.backend.definition` | Optional path to engine-specific configuration. |
| `engine.backend.dataframe` | Selects the dataframe backend. The built-in Engine supports `polars`. |
| `engine.backend.evaluation` | Reserved setting. It does not currently change evaluation behavior. |
| `engine.backend.batch_size` | Reserved setting. It does not currently change data access or batching. |
| `engine.preview_rows` | Maximum number of rows stored in the run preview. |

The backend must be compatible with the saved execution plan. An incompatible
configuration causes execution to fail rather than changing how the plan is
interpreted. Backend compatibility and configuration checks run regardless of
runtime validation mode.
