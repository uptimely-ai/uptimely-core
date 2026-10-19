# Backlog

Initially planned backend work by release version.

## Version 0.4.0

Mostly refactoring.

### Add id for datasets

Add explicit ID for datasets in Spec json document.

### Simplify compiled plan structure

Now contains the full spec definition. Consider having only stages, callables, execution groups, schedules etc execution related information while keeping spec.json separate.

### Rename mappings to calculations

This is more descriptive name than generic "mappings".

Also prepares naming conventions for upcoming validations.

### Improve engine run prints

Print selected datasets by `--print-datasets dataset_1 dataset_2`

Consider printing the datasets first rows eg by  `--print-rows 10`.

Now print is json chunk among other random details.

### Add config/compiler.json

Only allow `strategy="naive"` to create unoptimized plan.

### Improve project build prints

Now it says `Compiled 13 callables` which is uninformative.

Add something like:

```terminal
### BUILD ###

Completed in x.x seconds
Features: All
Build files: x/x/_generated/build


### SPECIFICATION ###

x Functions
x Entities
x Dimensions
x Datasets
x Features


### PLAN ###

Optimization strategy: Naive
x Stages
x Callables
```

### Improve explorer layout

* Review nav icon colors for plan and execution
* Rename data lineage to data animation
* Review the "Full build" box in top left nav panel

### Remove plan and spec version

Instead, just use build version for every generated document.

### Move manually maintained spec.json to build

If developer maintains spec.json instead spec.py by hand, copy the file to _generated folder as such, to keep strict convention.

### Consider adding Python decorators

* For spec and compiler validations
* Analytical functions
* CLI commands

## Version 0.5.0

### Add data quality validations

Now functions are expected to be in folder with name `functions`. Make default folder structure:

```sh
src
  /calculations
  /validations
```

The spec json will have top-level validations key and the current functions will be renamed to calculations.

Create similar argument binding for validations than calculations. Validations are expected to be on dataset level.

## Version 0.6.0

Engine refactoring and arrow support.

### Add Arrow support

Add support for Arrow in-memory format for tabular data.

Then supported formats would be Arrow and Polars (the backend engine).

## Version 0.7

### Add environment-aware builds and configuration overrides

Support explicit environment selection, such as dev and prod, with a shared base
configuration and environment-specific overrides. Define deterministic merge
rules and fail clearly when required configuration is missing.

Record the selected environment and non-sensitive configuration provenance in the
build manifest. Keep secrets out of generated plans and websites. Reuse the
compiled plan when only runtime bindings differ; runtime binding substitution
already exists.

## Undefined features

### Add preflight validation

Validate a saved plan, selected output scope, required runtime bindings, function
entrypoints, and backend compatibility without invoking analytical functions or
performing data reads or writes. Report actionable errors before execution.
Preflight does not guarantee source availability or validate actual input data.

### Add structured execution reports

Export a JSON run report with an execution ID, build and plan references,
per-callable statuses and durations, and failure details. Reuse the engine's
existing execution results and define a stable report format for CI, monitoring,
and later Explorer integration. Exclude credentials and dataset values by default.

### Add secret-aware runtime bindings

After environment-aware configuration overrides, support resolving sensitive
bindings from environment variables or a secret provider at runtime. Report
missing secrets explicitly and redact sensitive values from logs, errors, and
execution reports. Do not embed resolved secrets in build artifacts.

### Explore execution reports in Explorer

Investigate post-run inspection using structured execution reports, without
changing the static website architecture. A first version could load a report
through a local file picker and show callable statuses, timings, and failures
alongside the plan graph.

Verify that the report belongs to the displayed build and plan. Clearly
distinguish real execution results from the existing illustrative data animation.
Dataset schemas and row counts could be optional report metadata; actual values
and intermediate snapshots would require explicit opt-in capture, sampling
limits, and redaction. Live monitoring and shared run history are outside the
initial scope.

### Add optimization to compiler

Add optimization method to compiler configuration.

### Add freshness to spec

Defines how often each mapping or feature is needed.

Compiler can use this information to define scheduling eg by interval multiples.

### Higlight feature graph for selected feature

Highlight the features that the clickd feature depends on in explorer feature graph.


## Undefined refactoring

### Reuse spec validation functions

Use spec validations directly in unit tests instead of basically rewriting the same logic in unit tests.
