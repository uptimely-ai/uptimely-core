# Engine

An Engine executes a plan in a validated build bundle. It calls the Python
functions named by the plan, supplies their resolved arguments and runtime
data, and returns calculated outputs and execution details.

Engine is responsible of the correctness of the analytical execution considering specification declarations are right.

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
