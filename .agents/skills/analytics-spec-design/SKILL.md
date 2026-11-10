---
name: analytics-spec-design
description: "Design or author Uptimely analytics Specs and Python definitions. Use for profiles, dimensions, resolutions, grains, features, operators, bindings, calculations, or analytics project structure."
---

# Analytics Spec design

Use this workflow to translate analytical requirements into an Uptimely
definition. Consult the [Spec guide](../../../docs/overview/spec.md), the
[project structure guide](../../../docs/project-layout/project-structure.md),
and [pump analytics example](../../../examples/pump_analytics/README.md).

## Procedure

1. **Understand the question and data.** Identify the intended decision or
   metric, source tables/files, row meaning, key fields, units, time coverage,
   expected output, and important edge cases. Ask when an unknown could change
   the analytical result.
2. **Choose the observation grains.** For each profile, describe what one row
   represents. Put observation keys in dimensions and resolutions; put
   measured or calculated values in features. Do not assume the physical table
   layout must match the logical profile.
3. **Map calculations.** For each operation, list its input features, output
   features, required profile grain, and dependencies. Distinguish row-wise
   enrichment from aggregation and fragment production; use the documented
   binding and merge behavior.
4. **Specify data behavior.** Make units, null handling, duplicate keys,
   incomplete coverage, time-window boundaries, and aggregation semantics
   explicit when relevant. Do not invent defaults for domain rules.
5. **Author or recommend the definition.** Follow the existing Python or JSON
   authoring style in the target project. Keep runtime configuration and
   environment-specific locations outside the analytical definition.
6. **Verify.** If implementation was requested, run the narrowest relevant
   build or tests through Poetry. Report assumptions and any unverified
   expectations.
