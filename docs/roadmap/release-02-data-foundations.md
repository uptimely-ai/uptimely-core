# Release 2: Frame contracts, scoped runs, validation, and bounded concurrency

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Frame adapter contracts

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

## Work package: Runtime configuration and scoped execution

Run the requested scope with the right configuration without changing saved
builds. Named environments mean development, test, or production configuration,
not isolated function runtimes.

**Prerequisites:** Pinned dataset frame versions; Frame adapter contracts.

| title | breaking | description |
|---|---|---|
| Extend `uptimely run` | No | Add `--output`, `--head`, `--to` and `--bind`, with equivalent public `uptimely.run(...)` options and the established validation modes. Define output-scope pruning once using declared inputs and outputs and retain required producers. Do not exclude writes merely because validation is enabled or introduce a separate write-authorization policy. Writes within the requested scope execute like other steps. Optimization later reuses these semantics. |
| Add environment-aware builds and configuration overrides | No | Support named environments, deterministic layered configuration and clear errors for missing values. Use environment-specific parameters to configure write destinations, including non-production destinations for validation runs; validation does not automatically skip writes. Record environment and non-sensitive provenance, exclude secrets from artifacts, and reuse plans when only runtime bindings change. Apply overrides without mutating the published build. |
| Extend preflight validation | No | Extend mandatory capability preflight to saved-plan identity, output scope, runtime bindings, callable entrypoints and backend compatibility before execution. Reuse target-aware diagnostics without running analytical functions or performing workflow data I/O. This does not verify external source availability or input data. |
| Add secret-aware runtime bindings | No | Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets and keep them out of build artifacts. |

## Work package: Data quality validations

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

## Work package: Analytics CI/CD workflow

Provide a reproducible development workflow using the public testing helpers in
[the automated testing release](release-16-automated-testing.md). Fixture cases,
worked-example tables, and pytest integration are planned there rather than
embedded in the production specification.

**Prerequisites:** Runtime configuration and scoped execution, Data quality
validations, and Optional pytest integration. Existing repository tests continue to
accompany every software release.

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Expose and reuse specification validators in user tests instead of duplicating validation logic. |
| Document testing levels | No | Explain unit tests, named operator cases under `tests/uptimely/interface_data/`, controlled workflow tests, custom real-data checks under `tests/uptimely/quality/`, and runtime `validations/`. Keep fixture execution separate from production-data evaluation and document explicit side-effecting test opt-in. |
| Document an analytics CI/CD workflow | No | Provide a runnable pipeline that validates the spec, builds the plan, runs unit and fixture workflow tests with contract and quality checks, and publishes the build and available validation reports. Promote the same immutable build with runtime configuration supplied separately. Keep production-data checks and credentials outside fixture-based CI. |

## Work package: Plan optimization and bounded concurrency

Optimize a correct, scoped plan and execute genuinely independent work.

**Prerequisites:** Pinned dataset frame versions;
Frame adapter contracts; Runtime configuration and scoped execution;
Data quality validations for shared validation and failure semantics.

| title | breaking | description |
|---|---|---|
| Add compiler optimization | No | Offer configurable optimization that reuses scoped-execution pruning and avoids redundant assembly, conversion and materialization. Preserve dependencies derived from declared inputs and outputs, validation semantics and all writes within the requested scope. Keep the logical plan backend-independent, with backend-specific choices in target-aware planning. Retain safety checks with optimization disabled and test optimized/unoptimized equivalence. |
| Add a parallel scheduler | No | Run independent dataset work concurrently with configurable global and per-adapter limits and grouped lazy collection, such as `pl.collect_all`. Account for library threading, memory, process startup and serialization; do not allocate one process per callable or size workers solely from the widest stage. Wait for declared input producers to finish successfully before starting consumers, and preserve validation and failure propagation without special write skipping. Optimization and concurrency can ship separately if needed. |
