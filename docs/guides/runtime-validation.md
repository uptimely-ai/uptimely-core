# Validate execution

## Runtime validation

Runtime contract validation is opt-in. Enable it with `uptimely run --validate`
or `Engine.run(validate=True)` to check declared inputs and
dataframe contracts as each invocation executes. Checks include required
features, declared types, key uniqueness, row counts, coverage, and preservation
of existing rows, keys, values, and order where the invocation contract requires it.

Some checks on lazy frames must evaluate queries and may repeat upstream work,
so validation can add substantial runtime. It checks declared contracts, not
whether analytical results are correct.

Some structural checks always apply, even when runtime validation is disabled.
For example, results must have the required dataframe structure, declared
outputs, and expected merge schema. Configuration, saved-build integrity, and
backend compatibility are also always checked.

Native dataframe and function errors can also fail execution. Skipped checks
are not deferred to writes or final collection. Execution still runs configured
functions, including write sinks, and may have external side effects.
Missing or invalid builds report a recovery command.

See [Fragment and merge](../concepts/dataframes.md#fragments-and-datasets)
for merge-result requirements and
[Engine architecture](../concepts/engine.md#invocation-execution)
for execution order and failure handling.

## Runtime validation and configuration

Validation is a run option, not a project setting.
See [Configure a project](configuration.md#runtime-values) for runtime values,
paths, parameters, and backend settings.
