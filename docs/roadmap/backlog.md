# Backlog

Initially planned backend work by release version.

## Version 0.5.1 - Improve outputs

| title | breaking | description |
|---|---|---|
| Improve engine run output | No | Add options to list selected datasets and preview rows; make output easier to read than the current mixed JSON. |
| Improve build output | No | Report build duration, files, specification counts, optimization strategy, stages, and callables instead of only the callable count. |
| Drop dependency requirements for `escape` opreation | No | Now function with `escape` operation require that their input features are produced by a `read` operation. Drop this requirement. |

## Version 0.6.0 - Backend refactoring

Mostly refactoring.

| title | breaking | description |
|---|---|---|
| Flatten CLI api | Yes | Change eg `uptimely project build` --> `uptimely build` |
| Add dataset IDs | Yes | Give datasets explicit IDs in the specification. |
| Simplify compiled plans | Yes | Keep execution details in the plan and store the full specification separately. |
| Add `config/compiler.json` | No | Configure compiler behavior, initially supporting only `strategy="naive"`. |
| Review engine code | Maybe | Review the engine implementation. |
| Move spec types to module constants | No | Replace hard-coded specification types with module constants. |

## Version 0.6.1 - Explorer tuning

| title | breaking | description |
|---|---|---|
| Review Explorer navigation icon colors | No | Review the colors of navigation icons in Explorer. |
| Review the Explorer “Full build” panel | No | Review the Explorer “Full build” panel. |
| Rename “data lineage” to “data animation” in Explorer | No | Rename the “data lineage” label to “data animation” in Explorer. |
| Highlight feature dependencies | No | Show the selected feature's dependencies in Explorer's feature graph. |
| Modularize templates | No | If possible, move `js` and `css` to separate files |
| Add top nav bar | No | Standardizes views and prepare the layout for additional interaction. |

## Version 0.7.0 - Data quality validations

| title | breaking | description |
|---|---|---|
| Rename mappings to calculations | Yes | Use a clearer name and align terminology with planned validations. |
| Add data quality validations | No | Add dataset-level validations to the specification, give them calculation-style argument binding, and organize code under `calculations/` and `validations/`. |

## Version 0.7.1 - Environment overrides

| title | breaking | description |
|---|---|---|
| Add environment-aware builds and configuration overrides | No | Support named environments, deterministic layered configuration, and clear errors for missing values. Record the environment and non-sensitive provenance in the build manifest, exclude secrets from generated artifacts, and reuse plans when only runtime bindings change. |

## Version 0.7.2 - Arrow support

| title | breaking | description |
|---|---|---|
| Add Arrow support | No | Support Arrow as an in-memory tabular format alongside Polars. |

## Undefined features

| title | breaking | description |
|---|---|---|
| Add preflight validation | No | Check saved plans, output scope, runtime bindings, function entrypoints, and backend compatibility before execution—without running analytical functions or reading/writing data. This does not verify source availability or input data. |
| Add structured execution reports | No | Export stable JSON reports with execution IDs, build/plan references, per-callable status and duration, and failure details; exclude credentials and dataset values by default. |
| Add secret-aware runtime bindings | No | Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets, and keep them out of build artifacts. |
| Explore execution reports in Explorer | No | Load a report locally to show callable statuses, timings, and failures beside the plan graph. Verify build/plan identity and distinguish actual results from illustrative animation. Defer live monitoring and shared history; require explicit safeguards for capturing data values or snapshots. |
| Add compiler optimization | No | Configure the compiler's optimization method. |
| Add freshness to the specification | No | Define how often mappings or features are needed so the compiler can derive schedules. |
| Warn when unused features are declared | No | Change spec validation so unused declared features produce a warning instead of stopping the build. |

## Undefined refactoring

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Call the specification validators in unit tests instead of duplicating their logic. |
