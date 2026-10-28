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

## Running the example

For environment setup, commands to run each workflow, generated outputs, and
documentation preview instructions, see the shared [examples guide](../README.md).
The uncontrolled workflow writes
`_generated/pump_external_workflow_results.csv`; its declared `ratio` output is
not materialized as a dataframe column.
