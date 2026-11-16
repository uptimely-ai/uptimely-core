# Validate execution

## Runtime validation

Runtime contract validation is opt-in. Enable it with `uptimely run --validate`
or `Engine.run(validate=True)` to check declared inputs and
dataframe contracts as each invocation executes. Checks include required
features, declared types, key uniqueness, and preservation of existing rows,
keys, values, and order where the invocation contract requires it.

Some checks on lazy frames must evaluate queries and may repeat upstream work,
so validation can add substantial runtime. It checks declared contracts, not
whether analytical results are correct.

Some structural checks always apply, even when runtime validation is disabled.
For example, results must have the required dataframe structure, declared
outputs, and expected merge schema. Configuration, saved-build integrity, and
backend compatibility are also always checked.

## Runtime validation and configuration

Without `--validate`, the engine still binds arguments, stages fragments, and
calls their scheduled merge functions. It skips input-feature, declared type,
key uniqueness, row-count, and coverage checks. Merge results must still be
dataframes with the complete expected target schema, and overlapping feature
columns are rejected. Native dataframe and function errors can also fail
execution. Skipped checks are not deferred to writes or final collection. This runs the plan's
configured functions, including write sinks, and may have external side
effects. Missing or invalid builds report a recovery command.

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

Paths referenced by `$paths.<name>` must have an entry. Relative paths resolve
against the project root and absolute paths are preserved. Parameters referenced
by `$params.<name>` must also have an entry and are passed unchanged. Use
parameters for values such as optional filters, not file locations. The example
`env` parameter is not referenced by the Spec and can be overridden by a named
config.

See the [execution engine specification](../architecture/engine.md) for parameter
references and backend settings.
