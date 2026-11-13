# Analytical functions

Uptimely validates analytical function boundaries: argument and return
interfaces, dataframe schemas, feature dependencies, and merge relationships.
Developers remain responsible for the calculations inside those boundaries.

## Avoid loops

Prefer dataframe expressions over Python loops such as:

```py
for truck in trucks:
    x = process_single_truck()
    ...
```

Use vectorized expressions and dataframe or SQL windows where possible. If an
existing Python function needs each truck row as a tuple, Polars supports:

```py
result = df.map_rows(process_single_truck)
```

This still calls Python once per row. Prefer native dataframe expressions when possible.

Loops can be appropriate for simulations where each step depends on the previous result:

```py
for t in timesteps:
    results = complex_simulation_step(t, results)
    ...
```

## Keep analytical windows manageable

Choose the smallest window and coarsest resolution that preserve the analytical
meaning. Hundreds to a few thousand observations per entity are a useful starting
point. Above roughly 10,000, review aggregation and memory needs rather than
treating this as a hard limit.

For example, calculate each cooling pump's maximum differential pressure over the preceding 24 hours,
updating every minute:

| Input resolution | Calculation | Observations per full window |
| --- | --- | --- |
| Raw, one reading per second | Sliding maximum over raw readings | 86,400 |
| Bucketed, one maximum per minute | Sliding maximum over minute maxima | 1,440 |

Smaller windows also reduces row context for stateful calculations. Estimate memory across all
active entities, including late data and engine overhead, and verify it under load.

## Keep analytical calculations pure

Compute declared outputs from declared inputs without I/O, logging, or mutation
of input data or shared state. Keep source and sink communication separate.

Keep external workflows behind a clear boundary rather than mixing them into
analytical calculations. Make inputs, outputs, and side effects explicit so
calculations remain easy to test and reuse.

Test values, schemas, unchanged inputs, and domain invariants directly.
Contract validation cannot prove that arbitrary Python code is pure or correct.

## Do the heavy lifting in the source

Push filtering, column selection, large joins, deduplication, and suitable
pre-aggregation into the source query. Read only the slice the graph needs
instead of loading full tables into Python.

Use indexes and data partitions to make source queries efficient.

Expose identifiers and time ranges as read-function arguments. Bind their values
through the database driver rather than interpolating SQL strings.

## Read high quality data

When authorized, read data from high quality QA environemnt or production replica even for development and debugging. This helps to reproduce real issues
without manually maintaining duplicate datasets. Use read-only access and non-production write destinations.

Use non-production sources for schema changes, new algorithms, targeted debuggin, or data not yet available in production.
