# Development roadmap

Uptimely Core is evolving from batch-oriented analytics toward more reliable,
extensible execution and easier exploration of analytical dependencies.
Near-term work improves Explorer navigation and lineage views, then strengthens
data adapters, validation, configuration, and execution planning.

Longer term, the project aims to support freshness-aware and streaming
workflows, portable isolated runtimes, and user-selected orchestrators. The
first streaming engine will run bounded micro-batches and retain progress and
analytical state across invocations, without running as a server. Separately,
the execution engine can grow from single-process runs to segmented,
parallel, and multi-node execution. Declarative specification and project
tooling will continue to expand alongside these capabilities.

## Roadmap structure

The [planned releases](backlog.md) group related work packages in dependency
order. Each package lists its prerequisites, so unrelated work can proceed in
parallel. High-priority packages appear first within those constraints, and
independently scheduled extensions are identified separately.

Release groupings are planning labels, not software version numbers. Versions
are assigned when software releases are published. A package's *breaking*
column marks changes that require updates to specifications, projects,
functions, or commands.
