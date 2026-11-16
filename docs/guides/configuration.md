# Configure a project

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
