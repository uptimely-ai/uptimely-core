# Engine

An Engine executes a plan in a validated build bundle. It calls the Python
functions named by the plan, supplies their resolved arguments and runtime
data, and returns dataset aliases and execution details.

Analytical validation is optional. Targeted execution and calculated-feature
output summaries are not yet available.
`calculated_outputs` is `None` until those summaries are supported.

Engine does not compile or change the plan, it just runs it.

The same bundle can run with different runtime parameters and environment-specific resources.

## Engine's run environment

The engine is piece of Python code and executes in whatever runtime environment it is ran. Engine can be considered as an application of an execution worker.

As of now, engine has exactly 1 runtime where it runs in. Engine can be consider

Engine runs in a single process. It is limited by memory, cpu and storage it runs on.

## Plan argument resolving

Compiler has already resolved binding arguments for feature and dimensions references.

Engine still needs to resolve dataframe arguments, because those are available only during the execution.

## Plan execution

The plan groups function invocations into dependency-ordered stages. The
current Engine processes stages and invocations sequentially.

An invocation runs only after its prerequisites succeed. If one fails, execution stops,
remaining invocations are marked skipped, and the result includes the failure.

Plan invocations carry explicit function arguments and named
returns. Analytical semantics are separate from call routing. See the
[execution plan](../artifacts/execution-plan.md) for the format.

Configured read and write functions are ordinary function calls and may have
external side effects.

The Engine passes function returns unchanged to subsequent calls. Producers
must return the intended columns, and merge bindings must explicitly supply
any relation keys their merge functions need. The built-in default merge
binding receives relation keys in its explicit arguments.

## Dataframe backend

The plan declares the backend it requires, and the Engine checks compatibility
before execution. The built-in Engine supports the `polars` backend. Named
returns can hold any value, but saved dataframe previews require Polars
`DataFrame` or `LazyFrame` values.

## Engine configuration

Uptimely supplies the Engine with runtime configuration separately from the
Spec. A directly constructed Engine uses explicit settings and does not read
configuration files. For backend options, paths, and parameters, see
[Configure a project](../guides/configuration.md).
