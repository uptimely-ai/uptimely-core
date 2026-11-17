# Release 5: Freshness requirements and dependency-derived schedules

This is a planned release grouping, not a published software version.

## Work package: Freshness-aware scheduling

Derive schedules from declared result freshness without changing the meaning
of analytical dependencies.

**Prerequisites:** Pinned dataset frame versions, Scoped run options, Runtime
environments and preflight. Parallel execution is not required.

| title | breaking | description |
|---|---|---|
| Declare freshness requirements | No | Add freshness requirements to mappings or features and validate their values with actionable diagnostics. |
| Propagate freshness through dependencies | No | Derive output freshness from declared input/output dependencies and account for external source availability. Keep freshness separate from side-effect dependencies. |
| Validate schedule compatibility | No | Define schedule-multiple and compatibility rules, and reject incompatible freshness and schedule declarations. |
| Derive schedules from freshness | No | Add schedules derived from freshness only after the requirement and compatibility rules are established. Earlier work validates existing schedule declarations only. |
