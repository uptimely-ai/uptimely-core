---
layout: default
title: Example Project
nav_order: 4
---

# Pump analytics example

`example_1` is an end-to-end pump analytics project. It models pump assets and
telemetry, reads source datasets, calculates health and operational features,
and writes selected calculated telemetry features as JSON to standard output.
The engine returns the calculated feature IDs and runtime datasets.

## Example-specific behavior

Calculations consume features only from their own dataset. For example, the
bearing-temperature maximum and normalized health signal belong to the telemetry
dataset because their input columns originate there. Cross-dataset collapse,
expansion, and alignment are not implemented in this example.

The telemetry dataset declares ascending logical order by `timestamp`. This is
descriptive metadata, not a physical sorting guarantee; the temperature and
vibration delta calculations retain explicit timestamp-ordering inputs. The
pump-level dataset has no timestamp dimension or timestamp order.

The JSON specification in [`_generated/spec/spec.json`](_generated/spec/spec.json)
is read by the runners and used by the compiler, documentation generator,
feature graph, and engine.

## Running the example

For environment setup, commands to run each workflow, generated outputs, and
documentation preview instructions, see the shared [examples guide](../README.md).
