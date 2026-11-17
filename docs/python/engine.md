# Execution engine

## Engine and configuration

Use `Uptimely.run()` or `Uptimely.create_engine()` to apply project configuration. Constructing
`Engine` directly does not load a TOML file. Supply `EngineConfig`, parameters,
and paths explicitly when using it independently.

::: uptimely.engine.engine
    options:
      heading_level: 2
      show_root_heading: false
      members: [Engine]

::: uptimely.engine.config
    options:
      heading_level: 2
      show_root_heading: false
      members: [EngineConfig, EngineBackendConfig]
