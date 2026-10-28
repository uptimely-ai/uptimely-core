# Backlog

Planned releases are listed in the order we expect to publish them. Each
release names the work it needs first; unrelated work can happen at the same
time. Items that can be released separately are listed at the end.

Version numbers are assigned when releases are published. The *breaking*
column marks changes that require users to update their specifications,
projects, functions or commands.


## Planned release: Frame adapter contracts

Introduce a common adapter contract for converting and combining dataframe
representations. Keep Polars as the built-in native implementation, and use
adapters to support interoperability with other dataframe libraries.

**Prerequisites:** Pinned dataset frame versions.

| title | breaking | description |
|---|---|---|
| Refactor `DataFrameBackend` and `PolarsBackend` | No | Define the public `DataFrameBackend` interoperability contract with `evaluation: str` (`lazy` or `eager`), `data_types: list` (supported dataframe classes, such as `pd.DataFrame`), and `to_arrow`, `from_arrow` and `merge` methods. Refactor the existing Polars implementation as `PolarsBackend(DataFrameBackend)`. Keep additional operations needed by the engine in `PolarsBackend` without requiring them in the shared contract. |
| Add a public runtime adapter registry | No | Register adapters by the concrete dataframe types they support and the capabilities they provide. Keep adapters out of the analytical specification. Load trusted adapter modules explicitly through engine configuration; do not install packages or discover and execute arbitrary project modules automatically. |
| Declare function representation requirements | No | Document the data formats each function implementation expects and returns. Store this information with the implementation binding, not separately for each dataset or feature. Determine formats without relying only on type annotations or importing implementation code when signature validation is disabled. If a format is unknown, leave it unresolved rather than claiming a conversion adapter is missing. Keep the logical plan independent of the runtime backend, and make backend-specific conversion choices separately. |
| Define portable logical type compatibility | No | Define schema compatibility independently of physical dataframe types, using Arrow mappings at representable interchange boundaries. Document normalization such as string widths and equivalent time zones. Distinguish portable structured values from arbitrary Python objects and reject unsupported conversions explicitly. |
| Add Arrow boundary conversion | No | Use each adapter's `to_arrow` and `from_arrow` methods only across supported representation boundaries. Retain native frames on same-representation paths and preserve lazy plans where supported. Keep accumulated datasets in the selected assembly representation; convert incoming fragments once and outward only for consumers that require it. Document materialization, allocation and type limitations: Arrow transfers data, not lazy plans, and is not universally zero-copy. |
| Remove the engine dataframe setting | No | Remove `backend.dataframe` from engine configuration. Determine required conversions and fragment merges from functions' declared dataframe representations and the available adapters; keep Polars as the built-in native implementation. Conversion-only adapters permit foreign fragments without native merge support. If merging is required but unavailable for the involved representation, fail explicitly rather than silently falling back to Polars. |
| Validate adapter capabilities before execution | No | Record representation and capability requirements during portable compilation without requiring target adapters on the build machine. Offer strict target-aware compilation using engine configuration and the registry. Reuse its resolver in mandatory engine preflight to check conversions, native operations, execution requirements and permitted materialization or transfer boundaries. Errors identify the function or boundary, missing capability, expected registration signature and loading guidance. |
| Add adapter and assembly conformance suites | No | Generalize the existing Polars safety tests into reusable suites for conversion and native assembly separately. Cover null and duplicate keys, dimensionless datasets, collisions, partial coverage, schema fidelity, missing values and eager/lazy behavior. Test missing-capability diagnostics and reject unsupported boundaries without silent local collection. Ship suites with the registry; every later adapter must pass its applicable tests. |

## Planned release: Runtime configuration and scoped execution

Run the requested scope in the right environment without changing saved builds.

**Prerequisites:** Pinned dataset frame versions; Frame adapter contracts.

| title | breaking | description |
|---|---|---|
| Extend `uptimely run` | No | Add `--output`, `--head`, `--to` and `--bind`, with equivalent public `uptimely.run(...)` options and the established validation modes. Define output-scope pruning once using declared inputs and outputs and retain required producers. Do not exclude writes merely because validation is enabled or introduce a separate write-authorization policy. Writes within the requested scope execute like other steps. Optimization later reuses these semantics. |
| Add environment-aware builds and configuration overrides | No | Support named environments, deterministic layered configuration and clear errors for missing values. Use environment-specific parameters to configure write destinations, including non-production destinations for validation runs; validation does not automatically skip writes. Record environment and non-sensitive provenance, exclude secrets from artifacts, and reuse plans when only runtime bindings change. Apply overrides without mutating the published build. |
| Extend preflight validation | No | Extend mandatory capability preflight to saved-plan identity, output scope, runtime bindings, callable entrypoints and backend compatibility before execution. Reuse target-aware diagnostics without running analytical functions or performing workflow data I/O. This does not verify external source availability or input data. |
| Add secret-aware runtime bindings | No | Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets and keep them out of build artifacts. |

## Planned release: Data quality validations

Check real data with explicit rules that produce no features and do not change
data. Quality checks complement contracts; they do not prove formula correctness.

**Prerequisites:** Frame adapter contracts; Runtime configuration and scoped
execution for shared invocation and environment configuration.

| title | breaking | description |
|---|---|---|
| Separate mandatory and optional runtime checks | Yes | Keep preflight, actual returned-representation checks and assembly safety mandatory, including required columns, collisions and dimension-key uniqueness. Add `uptimely run --validate contracts` for extended actual-type and declared-data-contract checks, with the same named modes in the Python engine API rather than an ambiguous boolean. Use native capabilities, not unconditional Arrow copies; respect materialization policy. Unknown or not-yet-supported validation modes fail explicitly. |
| Add data quality validations | No | Add a `validations` section with calculation-style binding, organizing code under `calculations/` and `validations/`. Dataset validation functions return `bool` or failing rows, where an empty frame means passed. Severity `error` fails the run and stops further execution under the normal failure policy, without special write-only gating. Severity `warn` reports and continues. Validation runs include writes like other steps, using environment-configured destinations. Extend existing modes with `--validate quality` and `--validate all`, the latter including contract checks. Show validations as feature status badges in Explorer, not calculation steps. |
| Add reusable null-quality checks | No | Provide distinct any-null and all-null-column checks with explicit empty-dataset behavior and configurable severity. Apply only declared checks; nulls in a nullable column are not automatically invalid. Keep quality rules separate from mandatory assembly safety and reuse validation reporting. |
| Add a missing-value policy | No | Define whether datasets and features may contain nulls or NaNs, with feature-level settings overriding dataset defaults. Make the policy available to data-quality checks so allowed nulls are not treated as failures by default. Preserve nulls and NaNs distinctly across representation conversions, or reject conversions that cannot preserve them, such as arrays without null-validity information. |
| Add validation reports | No | Use a consistent record containing validation, dataset, severity, pass/fail, failing row count, bounded sample and message. Include run and build identity for later correlation with execution reports. Export with `--report <path>`, print a CLI summary and show the latest report in Explorer. Each run replaces the previous report; shared history is out of scope. Make sample capture explicit and redact sensitive data. |

## Planned release: Testing and CI/CD

Provide public testing helpers and a reproducible development workflow.

**Prerequisites:** Runtime configuration and scoped execution; Data quality
validations. Existing repository tests continue to accompany every release.

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Expose and reuse specification validators in user tests instead of duplicating validation logic. |
| Add the `uptimely.testing` pytest plugin | No | Provide a project fixture, workflow execution on fixture data with all validations and assertions showing failing rows. Include writes using test-environment destinations rather than automatically skipping them. Allow each data-quality validation to be collected as a separate pytest item in CI/CD. |
| Add worked examples | No | Store small input/output tables per function in the specification. Explorer shows before-and-after tables and the pytest plugin executes them as tests. |
| Document testing levels | No | Explain unit tests, worked examples, workflow tests on fixtures and real-data validations in the project structure guide, with `tests/unit/`, `tests/workflow/`, `tests/fixtures/` and `validations/` folders. |
| Document an analytics CI/CD workflow | No | Provide a runnable pipeline that validates the spec, builds the plan, runs unit and fixture workflow tests with contract and quality checks, and publishes the build and available validation reports. Promote the same immutable build with runtime configuration supplied separately. Keep production-data checks and credentials outside fixture-based CI. |

## Planned release: Plan optimization and bounded concurrency

Optimize a correct, scoped plan and execute genuinely independent work.

**Prerequisites:** Pinned dataset frame versions;
Frame adapter contracts; Runtime configuration and scoped execution;
Data quality validations for shared validation and failure semantics.

| title | breaking | description |
|---|---|---|
| Add compiler optimization | No | Offer configurable optimization that reuses scoped-execution pruning and avoids redundant assembly, conversion and materialization. Preserve dependencies derived from declared inputs and outputs, validation semantics and all writes within the requested scope. Keep the logical plan backend-independent, with backend-specific choices in target-aware planning. Retain safety checks with optimization disabled and test optimized/unoptimized equivalence. |
| Add a parallel scheduler | No | Run independent dataset work concurrently with configurable global and per-adapter limits and grouped lazy collection, such as `pl.collect_all`. Account for library threading, memory, process startup and serialization; do not allocate one process per callable or size workers solely from the widest stage. Wait for declared input producers to finish successfully before starting consumers, and preserve validation and failure propagation without special write skipping. Optimization and concurrency can ship separately if needed. |

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

Improve feature-lineage views and provide navigation for later inspection features.

**Prerequisites:** None within this backlog for standalone layout improvements.
Graph views must support the plan format available when they ship.

| title | breaking | description |
|---|---|---|
| Add top nav bar | No | Standardize navigation and provide extension points for report and explanation views. Only those extension points, not unrelated visual improvements, gate later views. |
| Add selectable specification lineages | No | Switch between combined, functions-only and features-only views. |
| Show dimension hierarchy in Explorer | No | Show dimension relationships instead of only a flat list. |
| Remove full argument texts from the invocation-lineage graph | No | Keep full argument text outside graph nodes, with details available separately. |
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

**Prerequisites:** Data quality validations for shared run/build identifiers;
Explorer navigation extension points for UI integration. Report export can
ship before its Explorer view.

| title | breaking | description |
|---|---|---|
| Add structured execution reports | No | Export stable JSON with execution identity, build/plan references, per-callable status and duration, and failure details. Correlate with validation reports through common identities while keeping their distinct purposes. Exclude credentials and dataset values by default. |
| Explore execution reports in Explorer | No | Load reports locally to show statuses, timings and failures beside the graph. Verify build/plan identity and distinguish actual results from illustrative animation. Defer live monitoring and shared history; require explicit safeguards for data values or snapshots. |

## Planned release: Freshness-aware scheduling

Derive schedules from declared result freshness without changing the meaning
of analytical dependencies.

**Prerequisites:** Pinned dataset frame versions; Runtime configuration and
scoped execution. Parallel execution is not required.

| title | breaking | description |
|---|---|---|
| Add freshness to the specification | No | Define freshness requirements for mappings or features, their propagation through declared input/output dependencies and how external source availability constrains achievable schedules. Specify schedule-multiple and compatibility rules without introducing separate side-effect dependencies. Reject incompatible requirements with actionable diagnostics. Add derived schedules only after these semantics are defined; earlier releases validate existing schedule declarations only. |

## Planned release: Example extensions

Consolidate and extend runnable analytics examples, not migration work deferred
from earlier releases.

**Prerequisites:** The function-kind contracts used by each example.

| title | breaking | description |
|---|---|---|
| Add signal processing to `pump_analytics` | No | Add NumPy-based signal processing and sliding-window calculations with meaningful aggregation and bounded windows. |

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

### Specification summary

**Prerequisites:** Existing specification model.

| title | breaking | description |
|---|---|---|
| Print a concise spec summary | No | Add a public `Spec.print_summary()` method that prints a readable overview of a specification, and demonstrate it in the project README's Python example. |

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

## Planned release: Reproducible builds and diagnostics

Make builds identifiable and immutable, and source-loading failures actionable.

**Prerequisites:** No new execution capability; provenance records must evolve
with changes to specification and plan formats.

| title | breaking | description |
|---|---|---|
| Record execution requirements | No | Record callable module references, declared package requirements and available version provenance in the build manifest. Provide checks for requirement availability and compatibility without executing analytical functions, for reuse by strict target-aware compilation and engine preflight. Distinguish declared requirements from best-effort import analysis; dynamic imports cannot be exhaustively inferred. Do not install dependencies automatically. |
| Preserve immutable build snapshots | No | Published artifacts retain fixed specification, mapping bindings, plan and callable implementation source with stable build identity. Package callable code in the bundle as a wheel for packaged projects or a source archive for supported pure-Python projects; record its content hash and load implementations from that artifact at runtime rather than mutable project files. An import path or source fingerprint alone does not freeze implementation. Record dependency requirements and provenance separately; bundling project source does not bundle third-party dependencies. Changed logic or bindings require a new build, not a new authoring identity for every function or mapping. Runtime overrides must not mutate published artifacts. |
| Improve build-source diagnostics | No | Distinguish malformed `module:attribute` entrypoints, missing spec sources and import failures inside otherwise valid modules. Preserve the underlying exception cause and actionable message, and offer a verbose traceback option. Cover Python and JSON source selection, project-directory discovery and nested import failures in tests; document the current CLI syntax rather than introducing a duplicate project-directory option. |
| Align examples with the documented project layout | Maybe | Link example READMEs to the project structure guide and keep specifications in `spec/`, separate from runtime configuration. Align examples and documentation around importable implementation packages, using a `src/` layout where packaging is needed and grouping I/O and calculations consistently. Add validation folders when quality validations ship. Keep deployment assets separate from analytical functions; automatic assembly needs no user-authored merge category. Update scaffolding, entrypoints, commands and tests together. Earlier breaking releases must still migrate affected examples immediately. |
