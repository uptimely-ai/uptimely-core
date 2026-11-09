---
layout: default
title: Example Project
nav_order: 4
---

# Pump analytics example

This example demonstrates a pump analytics workflow that uses asset and sensor
data to calculate health and operational metrics. It also includes an
uncontrolled workflow that reads pump measurements, calculates reference
ratios, and writes the results internally.

The Python modules import authoring classes and helpers directly from
`uptimely`, for example `from uptimely import Operator, Feature, Profile, ref`.
Functions use `from uptimely import function` and `@function` for analytical
contracts. Argument wiring uses `ref.dataset()`, `ref.feature()`, and
`ref.feature()`. Row-window binding helpers are imported separately from
`uptimely.spec.python.row_context`.

The telemetry profile binds `polars.LazyFrame.with_columns` directly to copy
`flow_rate` into `recommended_flow_rate`. Keyword argument names provide column
aliases, and feature references identify the source columns. `with_columns`
preserves all existing columns, as required by the `vectorize` contract.
This binding sets `validate_signature=False` because Polars uses annotation
names that are unavailable at runtime. Other functions retain signature
validation. The remaining recommendation fields use the struct-extraction
wrapper; the direct binding copies measured flow rather than extracting it
from the recommendation struct.

## Running the example

For environment setup, commands to run each workflow, generated outputs, and
documentation preview instructions, see the shared [examples guide](../README.md).
The uncontrolled workflow writes
`_generated/pump_external_workflow_results.csv` as a side effect. Its escape
operator belongs to the pump profile, which has the same machine grain. It
declares `measurement` and `reference_value` as logical inputs and `ratio` as a
logical output. These declarations do not implicitly pass a dataframe; this
function reads the input itself. The engine does not materialize `ratio`, and
the function's return value is ignored.
