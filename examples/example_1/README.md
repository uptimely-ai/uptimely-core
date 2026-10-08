---
layout: default
title: Example Project
nav_order: 4
---

# Example Project

`example_1` is an end-to-end pump analytics project. It models pump assets and telemetry, reads source datasets, calculates health and operational features, and writes the calculated telemetry features as JSON to standard output. The engine returns the calculated feature IDs and runtime datasets. The scripts also show how to compile a specification, generate documentation, render a feature graph, and execute a selected engine flow.

Calculations consume features only from their own dataset. For example, the bearing-temperature maximum and normalized health signal are part of the telemetry dataset because their input columns originate there. Cross-dataset collapse, expansion, and alignment are not implemented in this example.

## How the specification is read

The specification is stored as JSON in [`generated/spec/spec.json`](generated/spec/spec.json). Each runner resolves that path from the repository root and reads it with `Specification.from_json(...)`. The compiler, documentation generator, feature graph, and engine then operate on the resulting `Specification` object.

## How to run

Run these commands from the project root:

```sh
poetry run python examples/check_setup.py
poetry run python -m examples.example_1.run_execution_plan
poetry run python -m examples.example_1.run_docs
poetry run python -m examples.example_1.run_feature_graph
poetry run python -m examples.example_1.run_engine
```

Generated plans, HTML reports, graphs, and documentation are written to `generated/`. The engine runner returns the calculated feature IDs directly; the telemetry sink prints selected calculated columns as JSON and does not persist a calculated telemetry file.

Run `poetry run python examples/run_all.py` to execute all example workflows in one command. The scripts expect to be launched from the repository root.

The execution plan, feature graph, and engine commands show concise summaries by default. Add `--verbose` to inspect their dependency graphs, execution stages, or dataset registry.

## Folder structure

| Examples folder | Description |
| --- | --- |
| `run_*.py` | Scripts that demonstrate compilation, documentation, graph, plan, and engine workflows. |
| `spec` | Python declarations for the datasets. |
| `generated/spec` | The exported declarative analytics specification in `spec.json`. |
| `data` | JSON datasets used by the example's source functions. |
| `functions/source.py` | Functions that load source data. |
| `functions/calculation.py` | Functions that calculate derived features. |
| `generated` | Files produced by the example runners, grouped by workflow. |
