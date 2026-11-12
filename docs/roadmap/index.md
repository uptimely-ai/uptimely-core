# Development roadmap

Long term plans.


## Streaming

At the moment the framework is design for batch calculations.

We are planning to add streaming abstraction by data cache, watermarks and freshness.


## Support orchestrators

The built-in engine currently runs the graph in one Python process.

Plan isolated function runtimes under `runtimes/`, with implementations grouped
by runtime and dependencies provisioned separately from the developer's Poetry
environment. Inspect function contracts inside their owning runtimes and export
immutable ZIP bundles containing source, plans, and locked requirements.

Start with whole-graph jobs launched through a venv process or Docker. User-owned
functions under `deployment/` can submit the same bundle locally, to Prefect, or
to another orchestrator. Later, the compiler will identify execution segments
with Arrow IPC boundaries, and the engine will become a driver for sequential,
parallel, and multi-node worker execution.

See the [backlog](backlog.md) for dependency-ordered work packages.


## Extend the MCP support

Add MCP support for each atomic analytical functions.
