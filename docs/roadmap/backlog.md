# Backlog

Planned releases are listed in the order we expect to publish them. Each
release names the work it needs first; unrelated work can happen at the same
time. Items that can be released separately are listed at the end.

Version numbers are assigned when releases are published. The *breaking*
column marks changes that require users to update their specifications,
projects, functions or commands.

## Planned release: Function contracts

Clarify how calculations declare their inputs and outputs, and keep their
behavior focused on the intended calculation.

**Prerequisites:** None within this backlog.

| title | breaking | description |
|---|---|---|
| Analytical functions take only dependencies | Yes | Every feature reference in an analytical function's arguments represents an input dependency, not an output name or a feature label. Inputs are derived from structural binding arguments where possible. Keep explicit `inputs` for dependencies hidden inside procedures, including internal I/O in `escape` functions, independently of `validate_signature`. |
| Bind output features explicitly | Yes | Declare produced features through explicit `outputs` bindings; never infer outputs by parsing function arguments. Pass output-naming data in arguments as ordinary literal values, not `$features` references or Python `ref(...)` expressions, so output names do not create input dependencies. Update validation, documentation and examples together. |
| Keep analytical calculations pure | Yes | Calculation functions only compute and return their declared outputs from their declared inputs. They do not log, perform I/O, mutate inputs or shared state, or do unrelated work; operational side effects belong in explicit I/O operations or the engine. Document and test this coding contract without promising that signature checks or static analysis can prove arbitrary Python code pure. |
| Clarify validation ownership | No | Specification validation checks structure, references, dependencies, argument bindings, declared feature types and input/output contracts. Compilation checks plan feasibility, dependency ordering and existing schedule declarations; target-aware checks and freshness-derived schedules are added with their respective capabilities. The engine checks actual returned data and executes declared quality rules when supported. Reuse shared validators; runtime checks do not prove analytical correctness, which requires tests and domain-specific assertions. |
| Reject non-conforming functions with a hint | No | When a function does not fit its operation's contract, fail with a hint about which operation fits. Never relabel a function as `escape` automatically; `escape` is always an explicit choice. |
| Drop dependency requirements for `escape` operation | No | Remove the restriction that `escape` input features must be produced by `read`. Allow declared feature dependencies regardless of the producing operation, subject to normal producer and cycle checks. A `write` produces no features; ordering after an external write is a separate execution dependency. |
| Warn when unused features are declared | No | Change spec validation so unused declared features produce a warning instead of stopping the build. |

## Planned release: Specification parameters and binding semantics

Settle user-controlled values, bulk feature selection and external side-effect
ordering before expanding execution planning.

**Prerequisites:** Function contracts.

| title | breaking | description |
|---|---|---|
| Define constants in relation to parameters | No | Resolve whether constants are a special case of parameters before implementing the public model. Document ownership, scope and binding semantics for values such as `gravity_m2s: 9.81`, without mixing user-controlled values with calculated features. |
| Add parameters to the specification | No | Add parameters as a column type alongside dimensions and features, following the agreed constant model. A parameter is a control variable: it takes part in calculations and allows configuration per dimension, but is not modified during the process. |
| Pass all dataset features in one argument | No | Add `$datasets.@.features.ids` for feature names and `$datasets.@.features.dict` for names with metadata, optionally filtered by tags. Resolve the selected feature set deterministically from the specification, not incidental execution order. Include selected features in dependency analysis and reject self-dependencies and cycles rather than silently omitting unavailable features. |
| Declare external side-effect ordering | No | Add explicit execution-order dependencies when a step consumes external results created by another step, such as an `escape` reading persisted output from a `write`. Validate referenced steps and cycles, and preserve this ordering in sequential execution. Keep these edges distinct from feature dependencies and define required predecessor retention for later scoped execution and optimization. |
| Print a concise spec summary | No | Add a public `Spec.print_summary()` method that prints a readable overview of a specification, and demonstrate it in the project README's Python example. This item can ship independently of parameters. |

## Planned release: Dimensional operations and fragment foundation

Introduce fragment-producing operations together with the minimum safe Polars
assembly needed to execute them.

**Prerequisites:** Function contracts.

| title | breaking | description |
|---|---|---|
| Define operations by dimensional relationship | Yes | `read` ingests from an external source and takes no frames. `conform` brings in a dataset with the same dimensions but a different grain, for example different sampling. `collapse` brings in information from higher dimensionality, and `expand` from lower dimensionality. `conform` takes the foreign frame and the dataset's rows; `collapse` and `expand` take the foreign frame and, optionally, the dataset's rows. The compiler validates each relationship from declared dimensions. |
| Add dimension key selectors | No | Add `$datasets.@.dimensions.ids` for a dataset's key columns. Validate explicitly declared matching keys against the dimensions of the participating datasets; dimension references used for grouping or ordering are not automatically join keys. |
| Define and implement safe fragment assembly | No | Combine fragments of the same dataset by the owning entity's complete dimension key, never row position. Preserve full outer, one-to-one assembly with coalesced keys and null-key equality; retain keys present in only one fragment without claiming identical observation coverage. Define dimensionless assembly and feature collision rules. Ship native Polars assembly with mandatory required-column, key-uniqueness and collision checks, plus tests for partial coverage, null keys and dimensionless cases. No user-defined `paste` or per-dataset join function is required. Cross-dataset reconciliation remains an explicit dimensional operation. |
| Stage fragments | Yes | `read`, `conform`, `collapse` and `expand` return a fragment: the dataset's dimension keys plus the features they produce. They never join onto the dataset's frame. Ship the return-contract change together with working engine assembly using the current scheduler, without requiring the later function-level planner. |

## Planned release: Function-level planning and incremental assembly

Build dataset frames incrementally with explicit producer and frame-version
dependencies, keeping assembly in the engine.

**Prerequisites:** Dimensional operations and fragment foundation;
Specification parameters and binding semantics.

| title | breaking | description |
|---|---|---|
| Validate dataset assembly dependencies | No | Resolve unambiguous output producers, prerequisites and cycles in the function-level graph, including bulk feature selections and explicit execution-order edges. Retain all existing plan-safety checks throughout the transition; do not defer safety needed by the earlier fragment release. Physical key uniqueness and returned schemas remain runtime checks. |
| Build dataset frames function by function | Yes | Engine state is one frame per dataset. The plan is a graph of functions, with each function pinned to the foreign frame version it reads. Datasets in the same stage are independent only when no feature or execution-order dependency connects them. Start with a sequential scheduler and preserve the fragment assembly contract. |

## Planned release: Reproducible builds and diagnostics

Make builds identifiable and immutable, and source-loading failures actionable.

**Prerequisites:** No new execution capability; provenance records must evolve
with changes to specification and plan formats.

| title | breaking | description |
|---|---|---|
| Record execution requirements | No | Record callable module references, declared package requirements and available version provenance in the build manifest. Provide checks for requirement availability and compatibility without executing analytical functions, for reuse by strict target-aware compilation and engine preflight. Distinguish declared requirements from best-effort import analysis; dynamic imports cannot be exhaustively inferred. Do not install dependencies automatically. |
| Preserve immutable build snapshots | No | Published artifacts retain fixed specification, mapping bindings and plan snapshots with stable build identity. Record implementation package versions or source fingerprints so changed code can be detected; an import path alone does not freeze implementation. Changed logic or bindings require a new build, not a new authoring identity for every function or mapping. Runtime overrides must not mutate published artifacts. |
| Improve build-source diagnostics | No | Distinguish malformed `module:attribute` entrypoints, missing spec sources and import failures inside otherwise valid modules. Preserve the underlying exception cause and actionable message, and offer a verbose traceback option. Cover Python and JSON source selection, project-directory discovery and nested import failures in tests; document the current CLI syntax rather than introducing a duplicate project-directory option. |
| Align examples with the documented project layout | Maybe | Link example READMEs to the project structure guide and keep specifications in `spec/`, separate from runtime configuration. Align examples and documentation around importable implementation packages, using a `src/` layout where packaging is needed and grouping I/O and calculations consistently. Add validation folders when quality validations ship. Keep deployment assets separate from analytical functions; automatic assembly needs no user-authored merge category. Update scaffolding, entrypoints, commands and tests together. Earlier breaking releases must still migrate affected examples immediately. |

## Planned release: Frame adapter contracts

Keep Polars as the built-in native implementation. Separate dataframe conversion
from native assembly and validate both before advertising support.

**Prerequisites:** Function-level planning and incremental assembly;
execution-requirement checks from Reproducible builds and diagnostics.

| title | breaking | description |
|---|---|---|
| Add a public runtime adapter registry | No | Register operations by concrete frame representation and capability, such as `to_arrow`, `from_arrow` and `assemble_fragments`, with documented signatures. Keep adapters out of the analytical specification. Load trusted adapter modules explicitly through engine configuration; do not install packages or discover and execute arbitrary project modules automatically. |
| Integrate native execution adapters | Maybe | Evolve `DataFrameBackend` around the registry, retaining shared assembly orchestration and built-in Polars support. Native execution requires inspection, selection and contract validation as well as assembly. Limit the interface to engine requirements instead of creating a general dataframe API or compatibility-layer dependency. |
| Declare function representation requirements | No | Record input and output representations with implementation-binding metadata, not individual dataset or feature mappings. Resolve requirements without relying solely on annotations or importing implementations when signature validation is disabled. Treat unknown representations as unresolved requirements, not missing adapters. Keep the logical plan backend-independent and target-specific choices separate. |
| Define portable logical type compatibility | No | Define schema compatibility independently of physical dataframe types, using Arrow mappings at representable interchange boundaries. Document normalization such as string widths and equivalent time zones. Distinguish portable structured values from arbitrary Python objects and reject unsupported conversions explicitly. |
| Add a missing-value policy | No | Declare `nullable` and `NaN` handling as a dataset default, overridable per feature. Define preservation or explicit rejection at conversion boundaries, including array representations that cannot retain null validity information. Do not silently conflate nulls and NaNs. |
| Add Arrow boundary conversion | No | Use Arrow only across supported representation boundaries. Retain native frames on same-representation paths and preserve lazy plans where supported. Keep accumulated datasets in the selected assembly representation; convert incoming fragments once and outward only for consumers that require it. Document materialization, allocation and type limitations: Arrow transfers data, not lazy plans, and is not universally zero-copy. |
| Select assembly independently of interchange | No | Configure assembly in engine settings, defaulting to Polars. Conversion-only adapters permit foreign fragments without native join support. Native assembly requires the full execution capability set; missing capabilities fail explicitly rather than falling back silently to Polars. |
| Validate adapter capabilities before execution | No | Record representation and capability requirements during portable compilation without requiring target adapters on the build machine. Offer strict target-aware compilation using engine configuration and the registry. Reuse its resolver in mandatory engine preflight to check conversions, native operations, execution requirements and permitted materialization or transfer boundaries. Errors identify the function or boundary, missing capability, expected registration signature and loading guidance. |
| Add adapter and assembly conformance suites | No | Generalize the existing Polars safety tests into reusable suites for conversion and native assembly separately. Cover null and duplicate keys, dimensionless datasets, collisions, partial coverage, schema fidelity, missing values and eager/lazy behavior. Test missing-capability diagnostics and reject unsupported boundaries without silent local collection. Ship suites with the registry; every later adapter must pass its applicable tests. |

## Planned release: Runtime contract validation

Add extended runtime checks and consistent controls without weakening the
mandatory safety already shipped with fragments and adapters.

**Prerequisites:** Frame adapter contracts.

| title | breaking | description |
|---|---|---|
| Separate mandatory and optional runtime checks | Yes | Keep preflight, actual returned-representation checks and assembly safety mandatory, including required columns, collisions and dimension-key uniqueness. Add `uptimely run --validate contracts` for extended actual-type and declared-data-contract checks, with the same named modes in the Python engine API rather than an ambiguous boolean. Use native capabilities, not unconditional Arrow copies; respect materialization policy. Unknown or not-yet-supported validation modes fail explicitly. |
| Restrict functions to declared feature inputs | Yes | Pass only dimension keys and declared feature inputs, so hidden column reads fail. Warn about undeclared output columns. Preserve explicit output bindings and representation requirements across native and converted paths. |

## Planned release: Runtime configuration and scoped execution

Run the requested scope in the right environment without changing saved builds.

**Prerequisites:** Function-level planning and incremental assembly;
Reproducible builds and diagnostics; Runtime contract validation.

| title | breaking | description |
|---|---|---|
| Extend `uptimely run` | No | Add `--output`, `--head`, `--to` and `--bind`, with equivalent public `uptimely.run(...)` options and the established validation modes. Define output-scope pruning once: retain required feature and execution-order predecessors and normally skip `write` unless requested. Explicitly report and require authorization when a selected step needs a write predecessor, rather than silently running it or dropping the edge. Optimization later reuses these semantics. |
| Add environment-aware builds and configuration overrides | No | Support named environments, deterministic layered configuration and clear errors for missing values. Record environment and non-sensitive provenance, exclude secrets from artifacts, and reuse plans when only runtime bindings change. Apply overrides without mutating the published build. |
| Extend preflight validation | No | Extend mandatory capability preflight to saved-plan identity, output scope, runtime bindings, callable entrypoints and backend compatibility before execution. Reuse target-aware diagnostics without running analytical functions or performing workflow data I/O. This does not verify external source availability or input data. |
| Add secret-aware runtime bindings | No | Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets and keep them out of build artifacts. |

## Planned release: Data quality validations

Check real data with explicit rules that produce no features and do not change
data. Quality checks complement contracts; they do not prove formula correctness.

**Prerequisites:** Runtime contract validation; Runtime configuration and scoped
execution for shared invocation and write-gating semantics.

| title | breaking | description |
|---|---|---|
| Add data quality validations | No | Add a `validations` section with calculation-style binding, organizing code under `calculations/` and `validations/`. Dataset validation functions return `bool` or failing rows, where an empty frame means passed. Severity `error` fails the run and skips every affected dataset write, including a write required by an execution-order edge; block dependent steps rather than bypassing the failure. Severity `warn` reports and continues. Extend existing modes with `--validate quality` and `--validate all`, the latter including contract checks. Show validations as feature status badges in Explorer, not calculation steps. |
| Add reusable null-quality checks | No | Provide distinct any-null and all-null-column checks with explicit empty-dataset behavior and configurable severity. Apply only declared checks; nulls in a nullable column are not automatically invalid. Keep quality rules separate from mandatory assembly safety and reuse validation reporting. |
| Add validation reports | No | Use a consistent record containing validation, dataset, severity, pass/fail, failing row count, bounded sample and message. Include run and build identity for later correlation with execution reports. Export with `--report <path>`, print a CLI summary and show the latest report in Explorer. Each run replaces the previous report; shared history is out of scope. Make sample capture explicit and redact sensitive data. |

## Planned release: Testing and CI/CD

Provide public testing helpers and a reproducible development workflow.

**Prerequisites:** Runtime configuration and scoped execution; Data quality
validations. Existing repository tests continue to accompany every release.

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Expose and reuse specification validators in user tests instead of duplicating validation logic. |
| Add the `uptimely.testing` pytest plugin | No | Provide a project fixture, workflow execution on fixture data with all validations and assertions showing failing rows. Allow each data-quality validation to be collected as a separate pytest item in CI/CD. |
| Add worked examples | No | Store small input/output tables per function in the specification. Explorer shows before-and-after tables and the pytest plugin executes them as tests. |
| Document testing levels | No | Explain unit tests, worked examples, workflow tests on fixtures and real-data validations in the project structure guide, with `tests/unit/`, `tests/workflow/`, `tests/fixtures/` and `validations/` folders. |
| Document an analytics CI/CD workflow | No | Provide a runnable pipeline that validates the spec, builds the plan, runs unit and fixture workflow tests with contract and quality checks, and publishes the build and available validation reports. Promote the same immutable build with runtime configuration supplied separately. Keep production-data checks and credentials outside fixture-based CI. |

## Planned release: Plan optimization and bounded concurrency

Optimize a correct, scoped plan and execute genuinely independent work.

**Prerequisites:** Function-level planning and incremental assembly;
Frame adapter contracts; Runtime configuration and scoped execution;
Data quality validations for validation-gating semantics.

| title | breaking | description |
|---|---|---|
| Add compiler optimization | No | Offer configurable optimization that reuses scoped-execution pruning and avoids redundant assembly, conversion and materialization. Preserve feature and execution-order edges, validation semantics and authorized side effects. Keep the logical plan backend-independent, with backend-specific choices in target-aware planning. Retain safety checks with optimization disabled and test optimized/unoptimized equivalence. |
| Add a parallel scheduler | No | Run independent dataset work concurrently with configurable global and per-adapter limits and grouped lazy collection, such as `pl.collect_all`. Account for library threading, memory, process startup and serialization; do not allocate one process per callable or size workers solely from the widest stage. Preserve ordering, write gating and failure propagation. Optimization and concurrency can ship separately if needed. |

## Planned release: Additional dataframe adapters

Extend supported libraries without conflating interchange with native assembly.

**Prerequisites:** Frame adapter contracts and their conformance suites.
Parallel scheduling is not required for an adapter to ship.

| title | breaking | description |
|---|---|---|
| Add conversion adapters and native implementations as needed | No | Start with pandas interchange and add DuckDB and PyArrow support for concrete workflows. Document capabilities and run the applicable conformance suites; conversion does not imply native assembly. Polars remains the default. NumPy and PyTorch can be used inside function bodies without requiring tensor feature support. |
| Add a mixed-library dataframe example | No | Demonstrate user-written conversion decorators, explicit module loading and Polars assembly of foreign fragments. Show native pass-through, conversions, unsupported types and actionable missing-capability errors. |
| Show conversion and assembly points in Explorer | No | Display known representation changes, selected assembly implementations and materialization requirements. Mark unresolved boundaries explicitly rather than claiming the portable compiler can infer every conversion. |

## Planned release: Explorer navigation and readability

Improve lineage views and provide navigation for later inspection features.

**Prerequisites:** None within this backlog for standalone layout improvements.
Graph views must support the plan format available when they ship.

| title | breaking | description |
|---|---|---|
| Add top nav bar | No | Standardize navigation and provide extension points for report and explanation views. Only those extension points, not unrelated visual improvements, gate later views. |
| Add selectable specification lineage views | No | Switch between combined, functions-only and features-only lineage. |
| Show dimension hierarchy in Explorer | No | Show dimension relationships instead of only a flat list. |
| Remove full argument texts from the execution graph | No | Keep full argument text outside graph nodes, with details available separately. |
| Improve Explorer chart legends | No | Make legends clearer and easier to use across visualizations. |

## Planned release: Callable metadata and explanations

Describe implementations without replacing explicit analytical contracts.

**Prerequisites:** Function contracts for metadata; Explorer navigation
extension points for the explanation views. Metadata extraction can ship first.

| title | breaking | description |
|---|---|---|
| Extract callable metadata | No | Populate the function model with signatures, parameter and return annotations, and Google-style docstring descriptions, including `Args:` and `Returns:`. Keep metadata serializable and report signature inconsistencies. Reuse existing introspection and parsing. Documentation and annotations do not replace feature bindings or determine outputs. Respect portable compilation and optional signature-inspection behavior instead of requiring implementation imports everywhere. |
| Add explanations for non-experts | No | Extend metadata extraction with `Explanation:` and `Formula:` sections containing argument placeholders. Explorer fills them with bound feature descriptions and units and combines them into output lineage stories. |

## Planned release: Execution reports and inspection

Make execution outcomes portable and inspectable without promising live
monitoring or shared history.

**Prerequisites:** Reproducible builds and diagnostics; Data quality validations
for shared run/build identifiers; Explorer navigation extension points for UI
integration. Report export can ship before its Explorer view.

| title | breaking | description |
|---|---|---|
| Add structured execution reports | No | Export stable JSON with execution identity, build/plan references, per-callable status and duration, and failure details. Correlate with validation reports through common identities while keeping their distinct purposes. Exclude credentials and dataset values by default. |
| Explore execution reports in Explorer | No | Load reports locally to show statuses, timings and failures beside the graph. Verify build/plan identity and distinguish actual results from illustrative animation. Defer live monitoring and shared history; require explicit safeguards for data values or snapshots. |

## Planned release: Freshness-aware scheduling

Derive schedules from declared result freshness without changing the meaning
of analytical dependencies.

**Prerequisites:** Specification parameters and binding semantics;
Function-level planning and incremental assembly; Runtime configuration and
scoped execution. Parallel execution is not required.

| title | breaking | description |
|---|---|---|
| Add freshness to the specification | No | Define freshness requirements for mappings or features, their propagation through dependencies and how external source availability constrains achievable schedules. Specify schedule-multiple and compatibility rules, including explicit side-effect edges. Reject incompatible requirements with actionable diagnostics. Add derived schedules only after these semantics are defined; earlier releases validate existing schedule declarations only. |

## Planned release: Example extensions

Consolidate and extend runnable analytics examples, not migration work deferred
from earlier releases.

**Prerequisites:** The operation contracts used by each example; the documented
layout from Reproducible builds and diagnostics.

| title | breaking | description |
|---|---|---|
| Add signal processing to `pump_analytics` | No | Add NumPy-based signal processing and sliding-window calculations with meaningful aggregation and bounded windows. |
| Merge the escape example into `pump_analytics` | No | Incorporate the escape-operation demonstration into `pump_analytics` and remove the separate example project, updating links and tests. |

## Planned release: Distributed dataframe adapters

Add remote-native execution only for workflows that need it, after local
contracts, configuration, tests and diagnostics are established.

**Prerequisites:** Frame adapter contracts and conformance suites;
Runtime configuration and scoped execution; Testing and CI/CD;
Execution reports and inspection for report export, not its Explorer view.

| title | breaking | description |
|---|---|---|
| Add PySpark and Snowpark native execution support | No | Support cluster-native inspection, validation and assembly; Arrow conversion alone is not distributed execution. Keep frames and joins remote on native paths. Show remote-to-local transfer in the plan and require explicit permission, such as `uptimely run --allow-remote-transfer`, with transfer limits. Missing native capabilities must not implicitly collect into Polars. Test remote failure and transfer diagnostics and expose them in execution reports. |

## Independently scheduled releases and extensions

These are not blocked by the full preferred sequence above. Ship when their
specific prerequisites and user needs justify them.

### Polars 2.0 upgrade

**Prerequisites:** An available upstream release and successful compatibility
testing. Neither the upgrade nor the adapter redesign inherently blocks the other.

| title | breaking | description |
|---|---|---|
| Upgrade built-in Polars support to 2.0 | Maybe | Update the dependency range and adapt the built-in backend, tests and documentation to Polars 2.0. Assess breaking APIs and document migration for projects using Polars directly. |

### Specification composition

**Prerequisites:** Existing specification loading and semantic validation.
Keep merge rules independent of later execution capabilities.

| title | breaking | description |
|---|---|---|
| Merge JSON specification files | No | Read multiple JSON files and recursively merge objects before existing model and semantic validation. Accept identical overlaps; report conflicts with files and JSON paths. Arrays are whole values, not concatenated or deduplicated. Set the combined spec's name and source explicitly rather than merging contributor metadata. Fragments need not be semantically valid alone. Reuse reference, contract, producer and cycle checks. Do not add repository fetching, package discovery, version resolution, automatic namespacing or identifier rewriting. |

### Tensor features

**Prerequisites:** Frame adapter contracts, including portable type and
missing-value rules.

| title | breaking | description |
|---|---|---|
| Add a tensor feature type | No | Support fixed-shape tensor features using Arrow's `FixedShapeTensor` type, with explicit shape, dtype and conversion contracts tested through the applicable adapter conformance suites. |
