# Backlog

Planned backend work, grouped into planned releases. Releases are listed in
the order we intend to ship them. Version numbers are assigned when a release
is published, so the titles describe each release's theme instead. The
*breaking* column marks items that require changes to existing
specifications, projects, functions or CLI usage.

Releases are kept small, and each leaves the package in a working state.
The order follows dependencies:

1. Quick, non-breaking improvements come first.
2. Specification and plan clean-ups prepare for the larger changes.
3. Code resolution and function contracts are settled before the engine is
   rebuilt on top of them.
4. The engine becomes a pure orchestrator in two steps: staging fragments,
   then `paste`.
5. Runtime checks and frame adapters follow, then more dataframe libraries.
6. Data quality, testing, runtime configuration and authoring features build
   on the new engine.

## Planned release: Explorer polish

Small Explorer improvements that don't depend on backend changes.

| title | breaking | description |
|---|---|---|
| Review Explorer navigation icon colors | No | Review the colors of navigation icons in Explorer. |
| Review the Explorer “Full build” panel | No | Review the Explorer “Full build” panel. |
| Rename “data lineage” to “data animation” in Explorer | No | Rename the “data lineage” label to “data animation” in Explorer. |
| Highlight feature dependencies | No | Show the selected feature's dependencies in Explorer's feature graph. |

## Planned release: Specification and CLI clean-up

Breaking clean-ups that are easiest to make before the larger changes.

| title | breaking | description |
|---|---|---|
| Flatten CLI api | Yes | Change, for example, `uptimely project build` to `uptimely build`. |
| Add dataset IDs | Yes | Give datasets explicit IDs in the specification. |
| Move spec types to module constants | No | Replace hard-coded specification types with module constants. |

## Planned release: Plan format

Separate the plan from the specification, so later engine changes only touch
the plan.

| title | breaking | description |
|---|---|---|
| Simplify compiled plans | Yes | Keep execution details in the plan and store the full specification separately. |
| Add `config/compiler.json` | No | Configure compiler behavior, initially supporting only `strategy="naive"`. |

## Planned release: Code from installed packages

Make function code resolution predictable and versioned.

| title | breaking | description |
|---|---|---|
| Resolve entrypoints from installed packages | Yes | Analytics projects are installed packages, and entrypoints are `module.path:qualname` resolved with `importlib`. The build records each entrypoint's distribution name and version. Automatic `sys.path` handling and remote URL entrypoints are removed; code that isn't packaged yet is installed in editable mode. |
| Replace `validate_signature` with `integration` | Yes | The new `integration` field takes `native`, `opaque` or `external`. `native` code is imported, checked and run. `opaque` legacy code is run without signature checks and marked "unverified" in Explorer. `external` code isn't importable: it is cataloged for Explorer but not run. |

## Planned release: Function contracts

One breaking change to how calculations declare their features.

| title | breaking | description |
|---|---|---|
| Rename mappings to calculations | Yes | Use a clearer name and align terminology with planned validations. |
| Analytical functions take only dependencies | Yes | Every feature reference in an analytical function's arguments is an input or an output; feature labels are not allowed. Calculations declare `outputs`, and inputs are derived from the binding arguments, so the separate `inputs` list is removed. External catalog entries keep explicit inputs and outputs. |
| Reject non-conforming functions with a hint | No | When a function doesn't fit its operation's contract, the compiler fails with a hint about which operation fits. Functions are never relabeled as `escape` automatically; `escape` is always an explicit choice. |
| Drop dependency requirements for `escape` operation | No | Functions with the `escape` operation currently require their input features to be produced by a `read` operation. Drop this requirement. |

## Planned release: Dimensional operations

Define operations by their dimensional relationship, and let them stage data
instead of joining it.

| title | breaking | description |
|---|---|---|
| Define operations by dimensional relationship | Yes | `read` ingests from an external source and takes no frames. `conform` brings in a dataset with the same dimensions but a different grain, for example different sampling. `collapse` brings in information from higher dimensionality, and `expand` from lower dimensionality. `conform` takes the foreign frame and the dataset's rows; `collapse` and `expand` take the foreign frame and, optionally, the dataset's rows. The compiler validates each relationship from declared dimensions. |
| Add dimension key selectors | No | Add `$datasets.@.dimensions.ids` for a dataset's key columns. Any argument bound to `$dimensions.*.id` values is a join key; the compiler checks that bound keys are dimensions shared by both frames. |
| Stage fragments | Yes | `read`, `conform`, `collapse` and `expand` return a fragment: the dataset's dimension keys plus the features they produce. They never join onto the dataset's frame, so they don't need to know whether their data arrives first. In this release, the engine still combines fragments itself. |

## Planned release: The `paste` operation

The engine stops joining data and becomes a pure orchestrator.

| title | breaking | description |
|---|---|---|
| Add the `paste` operation | Yes | A new dataset-level operation that combines two frames of the same dataset: `paste(left, right, on)`, bound with `$datasets.@.paste.left` and `$datasets.@.paste.right`. `left` is the dataset's frame so far and `right` is the next fragment; the engine calls it once per additional fragment. The project declares a default `paste`, and datasets override it when needed. A `cardinality` field (default `1:1`) documents how the frames relate. For now the default is a full outer join on the dimension keys, which reproduces today's behavior; later it may be restricted so that `paste` doesn't add rows. `merge_fragment` and the backend join are removed. |
| Validate that each dataset builds into one frame | No | Before anything runs, the compiler checks that every fragment is pasted, each feature is produced exactly once and before it is used, and the dependency graph has no cycles. |
| Build dataset frames function by function | Yes | Engine state is one frame per dataset. The plan is a graph of functions, with each function pinned to the foreign frame version it reads. Datasets in the same stage are independent. Start with a sequential scheduler. |

## Planned release: Runtime contract checks

Make the engine's runtime checks opt-in and library-neutral.

| title | breaking | description |
|---|---|---|
| Add `pyarrow` to core | No | `pyarrow` is the common interchange format and becomes a core dependency. |
| Map feature types to logical Arrow types | No | Each feature type maps to a logical Arrow type. Schema checks compare logical types, so `string` equals `large_string` and `UTC` matches `Etc/UTC`. |
| Make runtime contract checks opt-in | Yes | Move the engine's runtime checks behind `uptimely run --validate contracts`, meant for local, development and CI/CD runs. Schema checks read metadata only; data checks (row counts, unique keys, unchanged values) run on an Arrow copy while the next function receives the original frame. Each function receives only the dimension keys plus its declared inputs, so hidden column reads fail. Undeclared output columns produce a warning. Runs without the flag perform no checks. |

## Planned release: Frame adapters

Decouple the engine from Polars.

| title | breaking | description |
|---|---|---|
| Replace `DataFrameBackend` with frame adapters | Maybe | A small `FrameAdapter` interface per dataframe library: schema, Arrow conversion and an optional cache hint. Start with the Polars adapter. |
| Add the Arrow interchange layer | No | Export any frame through the Arrow C stream interface and import it with the target library's adapter, chosen from the function's annotations. Frames pass through unchanged between functions that use the same library. |
| Make Polars optional | Yes | Polars becomes an optional extra, installed with `uptimely[polars]`. |

## Planned release: More dataframe libraries

Arrow is the shared contract between libraries, not the only frame type.

| title | breaking | description |
|---|---|---|
| Add DuckDB, PyArrow and pandas adapters | No | Polars and DuckDB are equal choices; pandas and PyArrow get thin adapters. Array and tensor libraries such as NumPy and PyTorch are used inside function bodies. |
| Show conversion points in Explorer | No | The compiler finds where connected functions use different libraries, and Explorer shows each conversion before anything runs. |
| Add a missing-value policy | No | Declare `nullable` and `NaN` handling as a dataset default, overridable per feature, because nulls don't survive conversion to arrays. |
| Add a backend conformance suite | No | Run every example on both Polars and DuckDB. |

## Planned release: Data quality validations

Validations check data quality on real data. They are a separate concept from
analytical functions: they produce no features and don't change data.

| title | breaking | description |
|---|---|---|
| Add data quality validations | No | Add a `validations` section to the specification, with calculation-style argument binding, and organize code under `calculations/` and `validations/`. Validations apply to datasets. A validation function returns `bool` or a frame of failing rows (empty means passed). Each has a severity: `error` fails the run and skips every `write` on the dataset, `warn` reports and continues. Validations run only with `uptimely run --validate quality`; `--validate all` also runs the contract checks. In Explorer, validations appear as status badges on the features they check, not as calculation steps. |
| Add validation reports | No | Turn every validation result into the same record: validation, dataset, severity, pass or fail, failing row count, a fixed-size sample of failing rows and a message. `--report <path>` writes the records to a file, the CLI prints a summary and Explorer shows the latest report. Each run replaces the previous report; no history is kept. |

## Planned release: Testing

Support unit tests, worked examples and workflow tests with pytest.

| title | breaking | description |
|---|---|---|
| Add the `uptimely.testing` pytest plugin | No | Provide a project fixture, a helper that runs the workflow on fixture data with all validations, and assertions that show failing rows in the test failure. In CI/CD, each specification validation can also be collected as a separate pytest item. |
| Add worked examples | No | Store small input and output tables per function in the specification. Explorer shows them as before-and-after tables, and the pytest plugin runs them as tests. |
| Document testing levels | No | Describe unit tests (one function, small frames), worked examples, workflow tests (full system on fixture data) and validations (full system on real data) in the project structure guide, with `tests/unit/`, `tests/workflow/`, `tests/fixtures/` and `validations/` folders. |

## Planned release: Runtime configuration

Run exactly what is needed, in the right environment.

| title | breaking | description |
|---|---|---|
| Extend `uptimely run` | No | Add `--output`, `--head`, `--to`, `--bind` and `--validate`, pruning the plan to the functions needed for the requested outputs and skipping `write` unless asked. Expose the same options in a public `uptimely.run(...)` Python API. |
| Add environment-aware builds and configuration overrides | No | Support named environments, deterministic layered configuration, and clear errors for missing values. Record the environment and non-sensitive provenance in the build manifest, exclude secrets from generated artifacts, and reuse plans when only runtime bindings change. |

## Planned release: Explorer layout

Prepare Explorer for the explanation features.

| title | breaking | description |
|---|---|---|
| Modularize templates | No | If possible, move `js` and `css` to separate files. |
| Add top nav bar | No | Standardize views and prepare the layout for additional interaction. |

## Planned release: Authoring and explanations

Make large datasets easy to author and every calculation easy to understand.

| title | breaking | description |
|---|---|---|
| Pass all dataset features in one argument | No | `$datasets.@.features.ids` gives a list of feature names and `$datasets.@.features.dict` gives names with metadata, both optionally filtered by tags. They resolve to the features available when the function runs, so they don't create cycles. |
| Add explanations for non-experts | No | Docstring `Explanation:` and `Formula:` sections with argument placeholders are extracted at build time. Explorer fills them with bound feature descriptions and units, and combines them into lineage stories for an output. |

## Undefined features

Ideas without a planned release yet.

| title | breaking | description |
|---|---|---|
| Add preflight validation | No | Check saved plans, output scope, runtime bindings, function entrypoints, and backend compatibility before execution—without running analytical functions or reading/writing data. This does not verify source availability or input data. |
| Add structured execution reports | No | Export stable JSON reports with execution IDs, build/plan references, per-callable status and duration, and failure details; exclude credentials and dataset values by default. |
| Add secret-aware runtime bindings | No | Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets, and keep them out of build artifacts. |
| Explore execution reports in Explorer | No | Load a report locally to show callable statuses, timings, and failures beside the plan graph. Verify build/plan identity and distinguish actual results from illustrative animation. Defer live monitoring and shared history; require explicit safeguards for capturing data values or snapshots. |
| Add compiler optimization | No | Configure the compiler's optimization method. |
| Add freshness to the specification | No | Define how often mappings or features are needed so the compiler can derive schedules. |
| Warn when unused features are declared | No | Change spec validation so unused declared features produce a warning instead of stopping the build. |
| Add a parallel scheduler | No | Run independent datasets of a stage in parallel, with concurrency limits per adapter and grouped collection of lazy outputs (for example `pl.collect_all`). |
| Compose specifications across packages | No | Each package publishes its specification JSON through an `uptimely.specs` entry point. A master project includes specifications by package and version range, merges them with namespaced IDs and depends only on exported features. |
| Add PySpark and Snowpark adapters | No | Frames stay in the cluster. A step that pulls a remote frame into a local library is shown in the plan and runs only with `uptimely run --allow-remote-transfer`. |
| Add a tensor feature type | No | Support fixed-shape tensor features using Arrow's `FixedShapeTensor` type. |
| Show external catalog entries in Explorer | No | Render `integration: external` functions as catalog-only nodes with owner, location and where they run. |
| Add parameters to the specification | No | Add parameters as a column type alongside dimensions and features. A parameter is a control variable: it takes part in calculations and allows configuration per dimension, but is not modified during the process. A constant could be used as a parameter. |
| Add constants to the specification | No | Add a `constants` section, for example `{"gravity_m2s": 9.81}`, referenced in binding arguments as `$constants.gravity_m2s`. Before implementing, evaluate whether constants are a special case of parameters, and whether constants and parameters belong with the data instead of in the specification. |

## Undefined refactoring

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Call the specification validators in unit tests instead of duplicating their logic. |
