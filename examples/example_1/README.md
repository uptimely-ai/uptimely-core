---
layout: default
title: Example Project
nav_order: 4
---

# Example Project

`example_1` is an end-to-end pump analytics project. It models pump assets and telemetry, reads source datasets, calculates health and operational features, and writes the calculated telemetry features as JSON to standard output. The engine returns the calculated feature IDs and runtime datasets. The scripts also show how to compile a specification, generate documentation, render a feature graph, and execute a selected engine flow.

Calculations consume features only from their own dataset. For example, the bearing-temperature maximum and normalized health signal are part of the telemetry dataset because their input columns originate there. Cross-dataset collapse, expansion, and alignment are not implemented in this example.

## How the specification is read

The telemetry dataset declares ascending logical order by `timestamp`. This is
descriptive metadata, not a physical sorting guarantee. The temperature and
vibration delta calculations retain their explicit timestamp ordering inputs.
The pump-level dataset and Example 2 have no timestamp dimension and do not
declare timestamp order.

The specification is stored as JSON in [`_generated/spec/spec.json`](_generated/spec/spec.json). Each runner resolves that path from the repository root and reads it with `Specification.from_json(...)`. The compiler, documentation generator, feature graph, and engine then operate on the resulting `Specification` object.

## How to run

Run these commands from the project root:

```sh
poetry run python examples/check_setup.py
poetry run python -m examples.example_1.run_export_spec
poetry run python -m examples.example_1.run_execution_plan
poetry run python -m examples.example_1.run_docs
poetry run python -m examples.example_1.run_feature_graph
poetry run python -m examples.example_1.run_engine
```

Generated plans, HTML reports, graphs, and documentation are written to `_generated/`. The engine runner returns the calculated feature IDs directly; the telemetry sink prints selected calculated columns as JSON and does not persist a calculated telemetry file.

`run_export_spec` writes the specification JSON and a standalone reference page
to `_generated/spec/`. `run_docs` creates a unified website in `_generated/docs/`:
open `index.html` to navigate between the specification, feature graph, and
execution plan. The standalone plan and graph runners remain available.
The Specification sidebar group links to separate Overview, Features, Dimensions,
and Functions pages. The standalone specification report still contains all
sections in one file.

For a local website preview:

```sh
poetry run uptimely docs generate --spec examples/example_1/_generated/spec/spec.json --output examples/example_1/_generated/docs
poetry run uptimely docs serve --directory examples/example_1/_generated/docs
```

Visit `http://localhost:8001/`. The pages currently use externally hosted styling,
fonts, icons, and visualization libraries.

Run `poetry run python examples/run_all.py` to execute all example workflows in one command. The scripts expect to be launched from the repository root.

The execution plan, feature graph, and engine commands show concise summaries by default. Add `--verbose` to inspect their dependency graphs, execution stages, or dataset registry.

## Folder structure

| Examples folder | Description |
| --- | --- |
| `run_*.py` | Scripts that demonstrate compilation, documentation, graph, plan, and engine workflows. |
| `spec` | Python declarations for the datasets. |
| `_generated/spec` | The exported specification in `spec.json` and standalone reference in `spec.html`. |
| `_generated/docs` | Website index, specification, feature graph, execution plan, and reference JSON. |
| `data` | JSON datasets used by the example's source functions. |
| `functions/source.py` | Functions that load source data. |
| `functions/calculation.py` | Functions that calculate derived features. |
| `_generated` | Files produced by the example runners, grouped by workflow. |
