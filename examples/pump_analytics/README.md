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
`uptimely`, for example `from uptimely import Action, Dataset, Feature, ref`.
Functions use `from uptimely import function` and `@function` for analytical
contracts. Argument wiring uses `ref.dataframe()`, `ref.column()`, and
`ref.output()`. Row-window binding helpers are imported separately from
`uptimely.spec.python.row_context`.

## Running the example

For environment setup, commands to run each workflow, generated outputs, and
documentation preview instructions, see the shared [examples guide](../README.md).
The uncontrolled workflow writes
`_generated/pump_external_workflow_results.csv`; its declared `ratio` output is
not materialized as a dataframe column.
