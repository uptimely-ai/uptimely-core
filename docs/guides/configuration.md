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

## Runtime values

The `engine` section is validated as `EngineConfig` and contains backend
settings:

```json
{
  "backend": {}
}
```

Put file and directory locations in `paths`, and scalar runtime values in
`params`:

```json
{
  "engine": {"backend": {}},
  "paths": {
    "source_path": "data/input.parquet"
  },
  "params": {
    "env": "dev"
  }
}
```

Use parameters for values such as optional filters, not file locations. The example
`env` parameter is not referenced by the Spec and can be overridden by a named
config.

See the [configuration reference](../reference/configuration.md#configuration-sections)
for a complete TOML file, accepted settings, and runtime resolution rules.
