# Configure a project

## Select a configuration

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

## Configuration values

Configuration files use TOML. The supported tables, settings, and value
constraints are listed in the
[configuration file format reference](../artifacts/configuration.md).
The [example project's `uptimely.toml`](https://github.com/uptimely-ai/uptimely-core/blob/main/example/uptimely.toml)
shows a complete project configuration.

```toml
[application]
yaml_spec = "spec"

[code]
language = "python"
requirements = "pyproject.toml"
src = "src"

[test]
path = "tests"

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

### Application settings

Set one of `application.python_spec`, `application.json_spec`, or
`application.yaml_spec` to select a specification source. `python_spec` uses
the `MODULE:ATTRIBUTE` entrypoint format. `json_spec` is a JSON file path or a
directory containing `spec.json`. `yaml_spec` is a YAML file or directory path.
Paths are relative to the project
root unless absolute. See [Specification source discovery](build.md#specification-source-discovery)
for automatic selection and ambiguous-source errors.

### Code settings

`code.language` identifies the project code language and defaults to `python`.
`code.requirements` selects a requirements definition file relative to the project
root unless absolute. The file must exist. If omitted, the build uses
`requirements/pyproject.toml` when present, otherwise it extracts Python requirements
from the project root's `pyproject.toml` if available.

`code.src` is a Python source directory, relative to the project
root unless absolute. If omitted, it defaults to `src`. CLI values for the
specification source and source path override the corresponding settings. A
CLI specification source overrides the configured source. Explicit
Python method arguments also override the corresponding project settings.

The project root is not configured in `uptimely.toml`. The CLI's positional
project directory or `--project-root` selects it. If neither is given,
Uptimely uses the current working directory. The root is needed to locate the
configuration file in the first place.

Feature selection, build-before-run, log level, and analytical runtime validation
are command-specific options rather than project settings.

### Test settings

`test.path` selects the test directory relative to the project root or as an
absolute path. It defaults to `tests`. The `uptimely test` command
runs the JSON cases in that directory against the saved build. See
[`uptimely test`](../cli/project.md#uptimely-test).

### Runtime values

Put file and directory locations in `paths`, and scalar runtime values in
`params`. Specs reference them as `$paths.<name>` and `$params.<name>`.
Configured paths must have an entry. Relative paths resolve against the
project root. Absolute paths are preserved. Parameter values pass through to
functions unchanged. Missing values for required parameters fail when the
corresponding function is invoked.

Use parameters for values such as optional filters, not file locations.

### Engine settings

The `[engine]` section includes `preview_rows`, the default maximum number of
rows stored in the run preview. It defaults to `5`. The `--preview ROWS` CLI
option overrides it, while bare `--preview` uses the configured value.

Backend settings live under `[engine.backend]`. `type` names the configured
engine environment, and `definition` optionally supplies its engine-specific
configuration. `dataframe` selects the dataframe backend. The built-in Engine
supports `polars`. `evaluation` and `batch_size` are reserved settings and do
not currently change evaluation or data access behavior.

The backend must be compatible with the saved execution plan. An incompatible
configuration causes execution to fail rather than changing how the plan is
interpreted. Backend compatibility and configuration are checked before
execution.
