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
`ref.fragment()` for merge inputs. Row-window binding helpers are imported separately from
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

The spec also includes maximum-bearing-temperature rollups by pump series,
pump category, minute, hour, and day. Each is a single aggregation from the
minute telemetry profile. The asset registry contains six pumps across
five series (`SERIES-1` through `SERIES-5`) and three categories (`CAT-1` through `CAT-3`);
all individual pumps belong to the shared `Pump` profile. Profile `scope` labels are
descriptive metadata and do not change how other profiles or constants are
resolved.

### Capacity defaults by machine resolution

The asset files `data/pump_assets.json`, `data/pump_series.json`, and
`data/pump_category.json` declare nullable `max_capacity` values in m3/h at
pump, series, and category resolution. Their locations are runtime parameters
in `config/config.json`. The generic `source.read_file` function reads simple
JSON and CSV sources for capacities, constants, and external workflow inputs.
It reads all columns by default; optional `columns` selects source columns
and `rename` maps them to feature IDs after selection. Optional `schema` maps
source column names to `float`, `integer`, `string`, or `boolean`, preserving
declared types even for all-null capacities. Unsupported extensions and column
types raise an error. Telemetry retains its specialized reader for joins and derived
columns. For capacities,
expansion operators use the generic `analytics.select_columns` function to select
capacity columns together with their series or category identifiers and optionally
rename the selected columns. The pump reader retains those identifiers from the asset
registry, and automatic merging left-joins each fragment on its identifiers.
The runtime `Merge` owns assembly and collision/result checks; `Fragment` carries
the selected data and identifiers, while `Dataset` owns the accumulated pump data.
Series and category IDs are dimension identifiers, not pump features: the
pump read function returns them with the other asset columns, and the engine
retains all present resolution keys for the dimensions used by the profile grain.
The expansion functions do not read files or perform joins. Feature IDs are unique across profiles, so series and
category capacities are published as `max_capacity_series` and
`max_capacity_category`.

The pump profile keeps the three source capacities and resolves `max_capacity`
using the first non-null value in this order: **pump, series, category**.
Specificity, not the largest numeric capacity, determines the result. A zero
capacity is a valid override; if every resolution is missing, the result stays
null. The sample resolves PUMP-101 to its individual capacity of 125 m3/h
(overriding its series value of 130), and PUMP-201 to the category default of
100 m3/h because its pump and series capacities are null.

| Pump | Series | Category | Resolved capacity (m3/h) | Value source |
| --- | --- | --- | --- | --- |
| PUMP-101 | SERIES-1 | CAT-1 | 125 | Pump |
| PUMP-102 | SERIES-1 | CAT-1 | 130 | Series |
| PUMP-201 | SERIES-2 | CAT-1 | 100 | Category |
| PUMP-301 | SERIES-3 | CAT-2 | 190 | Pump |
| PUMP-302 | SERIES-4 | CAT-2 | 220 | Category |
| PUMP-401 | SERIES-5 | CAT-3 | 70 | Series |

Telemetry contains 10 records across all six pumps: two readings each for
PUMP-101, PUMP-102, PUMP-301, and PUMP-302, and one each for PUMP-201 and
PUMP-401. External workflow inputs remain available only for PUMP-101 and
PUMP-201; the other pumps have null external-input features.

## Running the example

For environment setup, commands to run each workflow, generated outputs, and
documentation preview instructions, see the shared [examples guide](../README.md).
The uncontrolled workflow writes
`_generated/pump_external_workflow_results.csv` as a side effect. Its escape
operator belongs to the pump profile, which has machine grain. It
declares `measurement` and `reference_value` as logical inputs and `ratio` as a
logical output. These declarations do not implicitly pass a dataframe; this
function reads the input itself. The engine does not materialize `ratio`, and
the function's return value is ignored.
