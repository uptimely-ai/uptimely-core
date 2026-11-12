# Release 5: Freshness requirements and dependency-derived schedules

This is a planned release grouping, not a published software version.

## Work package: Freshness-aware scheduling

Derive schedules from declared result freshness without changing the meaning
of analytical dependencies.

**Prerequisites:** Pinned dataset frame versions; Runtime configuration and
scoped execution. Parallel execution is not required.

| title | breaking | description |
|---|---|---|
| Add freshness to the specification | No | Define freshness requirements for mappings or features, their propagation through declared input/output dependencies and how external source availability constrains achievable schedules. Specify schedule-multiple and compatibility rules without introducing separate side-effect dependencies. Reject incompatible requirements with actionable diagnostics. Add derived schedules only after these semantics are defined; earlier work packages validate existing schedule declarations only. |
