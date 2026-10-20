# Backlog

Initially planned backend work by release version.

## Version 0.5.0 - Spec improvements

Spec lookup improvements.

* **Move spec folder to top level.** Now it is in config folder.
- **Move hand-maintained `spec.json` into the build.** Copy it to `_generated` to keep generated files consistently located.
- **Search spec automatically from project.** Search from the pre-defined spec folder.
- **Remove plan and spec versions.** Use the build version for all generated documents.


## Version 0.6.0 - Improve outputs

- **Improve engine run output.** Add options to list selected datasets and preview rows; make output easier to read than the current mixed JSON.
- **Improve build output.** Report build duration, files, specification counts, optimization strategy, stages, and callables instead of only the callable count.

## Version 0.7.0 - Backend refactoring

Mostly refactoring.

- **Add dataset IDs.** Give datasets explicit IDs in the specification.
- **Simplify compiled plans.** Keep execution details in the plan and store the full specification separately.
- **Add `config/compiler.json`.** Configure compiler behavior, initially supporting only `strategy="naive"`.
- Review engine code
- Move spec types to module constants from hard coded values

## Version 0.8.0 - Explorer tuning

- **Review Explorer navigation icon colors.**
- **Review the Explorer “Full build” panel.**
- **Rename “data lineage” to “data animation” in Explorer.**

## Version 0.9.0 - Data quality validations

- **Rename mappings to calculations.** Use a clearer name and align terminology with planned validations.
- **Add data quality validations.** Add dataset-level validations to the specification, give them calculation-style argument binding, and organize code under `calculations/` and `validations/`.

## Version 0.10.0 - Environment overrides

- **Add environment-aware builds and configuration overrides.** Support named environments, deterministic layered configuration, and clear errors for missing values. Record the environment and non-sensitive provenance in the build manifest, exclude secrets from generated artifacts, and reuse plans when only runtime bindings change.

## Version 0.11.0 - Arrow support

- **Add Arrow support.** Support Arrow as an in-memory tabular format alongside Polars.

## Undefined features

- **Add preflight validation.** Check saved plans, output scope, runtime bindings, function entrypoints, and backend compatibility before execution—without running analytical functions or reading/writing data. This does not verify source availability or input data.
- **Add structured execution reports.** Export stable JSON reports with execution IDs, build/plan references, per-callable status and duration, and failure details; exclude credentials and dataset values by default.
- **Add secret-aware runtime bindings.** Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets, and keep them out of build artifacts.
- **Explore execution reports in Explorer.** Load a report locally to show callable statuses, timings, and failures beside the plan graph. Verify build/plan identity and distinguish actual results from illustrative animation. Defer live monitoring and shared history; require explicit safeguards for capturing data values or snapshots.
- **Add compiler optimization.** Configure the compiler's optimization method.
- **Add freshness to the specification.** Define how often mappings or features are needed so the compiler can derive schedules.
- **Highlight feature dependencies.** Show the selected feature's dependencies in Explorer's feature graph.
- **Only warning when unused features declared.** Now the stop the build in spec validation.


## Undefined refactoring

- **Reuse specification validation functions.** Call the specification validators in unit tests instead of duplicating their logic.
