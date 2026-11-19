# Engine

The Engine executes the plan in a validated build bundle. It calls the Python
functions named by the plan, supplies their resolved arguments and runtime
data, and returns calculated outputs and execution details. It does not compile
or change the plan. The same bundle can run with different runtime parameters
and environment-specific resources.

## Invocation execution

The plan groups function invocations into dependency-ordered stages. The
current Engine processes stages and invocations sequentially. An invocation
runs only after its prerequisites succeed. If one fails, execution stops,
remaining invocations are marked skipped, and the result includes the failure.
Configured read and write functions are ordinary function calls and may have
external side effects.

## Dataframe backend

The plan declares the backend it requires, and the Engine checks compatibility
before execution. The built-in Engine supports the `polars` backend. Data
functions must return Polars `DataFrame` or `LazyFrame` values. Other dataframe
libraries and custom adapters are not supported.

## Engine configuration

Uptimely supplies the Engine with runtime configuration separately from the
Spec. A directly constructed Engine uses explicit settings and does not read
configuration files. For backend options, paths, and parameters, see
[Configure a project](../guides/configuration.md).

## Learn more

See the [Compiler](compiler.md) and [Execution plan](../artifacts/execution-plan.md)
references, the [`uptimely run` CLI reference](../cli/engine.md) for run
options and artifacts, and the [Python Engine API](../python/engine.md)
for programmatic execution and result access.
