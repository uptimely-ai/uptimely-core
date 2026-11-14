# Release 2: Frame contracts, scoped runs, validation, and bounded concurrency

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Dataframe adapter API and registry

Introduce a common adapter contract for converting and combining dataframe
representations. Keep Polars as the built-in native implementation, and use
adapters to support interoperability with other dataframe libraries.

**Prerequisites:** Pinned dataset frame versions.

| title | breaking | description |
|---|---|---|
| Define the `DataFrameBackend` contract | No | Define `evaluation` (`lazy` or `eager`), supported `data_types`, and `to_arrow`, `from_arrow`, and `merge` methods. |
| Refactor the Polars backend | No | Implement the contract as `PolarsBackend(DataFrameBackend)`. Keep engine-specific operations out of the shared contract. |
| Register adapter types and capabilities | No | Register adapters by the concrete dataframe types they support and the capabilities they provide. Keep adapters out of the analytical specification. |
| Load trusted adapters explicitly | No | Load modules through engine configuration. Do not install packages or discover and execute arbitrary project modules automatically. |

## Work package: Function representation and type contracts

Declare the data representations functions require and the logical types that
can cross adapter boundaries.

**Prerequisites:** Dataframe adapter API and registry.

| title | breaking | description |
|---|---|---|
| Declare function input and output representations | No | Record expected and returned formats with each implementation binding, not on datasets or features. Do not rely only on annotations or import code when signature validation is disabled. |
| Resolve unknown representations safely | No | Leave unknown formats unresolved rather than reporting a missing adapter. Keep the logical plan backend-independent and choose conversions separately. |
| Define portable logical type compatibility | No | Define schema compatibility independently of physical dataframe types, using Arrow mappings at supported interchange boundaries. |
| Normalize portable type differences | No | Document normalization such as string widths and equivalent time zones. Distinguish portable structured values from arbitrary Python objects and reject unsupported conversions. |

## Work package: Arrow conversion and assembly

Convert only at supported representation boundaries and preserve native
execution where possible.

**Prerequisites:** Function representation and type contracts.

| title | breaking | description |
|---|---|---|
| Convert across supported representation boundaries | No | Use adapter `to_arrow` and `from_arrow` methods only where representations differ and conversion is supported. |
| Preserve native and lazy execution paths | No | Retain native frames on same-representation paths and preserve lazy plans where supported. |
| Assemble fragments in the selected representation | No | Keep accumulated datasets in the selected assembly representation. Convert incoming fragments once and convert outward only for consumers that require it. |
| Document Arrow materialization limits | No | Explain allocation and type limits. Arrow transfers data, not lazy plans, and is not universally zero-copy. |

## Work package: Engine representation selection

Choose conversions and fragment assembly from declared function requirements
instead of a global dataframe setting.

**Prerequisites:** Arrow conversion and assembly.

| title | breaking | description |
|---|---|---|
| Remove the engine dataframe setting | No | Remove `backend.dataframe` from engine configuration. Keep Polars as the built-in native implementation. |
| Select conversions from declared representations | No | Determine required conversions and fragment merges from function-declared dataframe representations and available adapters. |
| Allow conversion without native assembly | No | Permit conversion-only adapters to supply foreign fragments when native merge support is not needed. |
| Report missing native merge support | No | Fail explicitly when required merging is unavailable. Do not silently fall back to Polars. |

## Work package: Adapter capability preflight

Resolve target-specific adapter capabilities before executing workflow data.

**Prerequisites:** Engine representation selection.

| title | breaking | description |
|---|---|---|
| Compile portable adapter requirements | No | Record representation and capability requirements without requiring target adapters on the build machine. |
| Add target-aware adapter validation | No | Offer strict compilation using engine configuration and the registry. Report the affected function or boundary, missing capability, expected registration signature, and loading guidance. |
| Check adapter requirements during preflight | No | Reuse the resolver to check conversions, native operations, execution requirements, and permitted materialization or transfer before execution. |

## Work package: Adapter conformance suites

Provide reusable tests that every built-in or future adapter can run.

**Prerequisites:** Dataframe adapter API and registry, Arrow conversion and
assembly, and Adapter capability preflight.

| title | breaking | description |
|---|---|---|
| Add conversion conformance tests | No | Create reusable adapter tests for schema fidelity, missing values, eager/lazy behavior, and unsupported conversions. |
| Add native assembly conformance tests | No | Cover null and duplicate keys, dimensionless datasets, collisions, partial coverage, and supported assembly behavior. |
| Test missing capabilities and publish suites | No | Verify actionable diagnostics and reject unsupported boundaries without silent local collection. Ship applicable suites with the registry for future adapters. |

## Work package: Scoped run options

Run only the requested outputs while preserving required producers and writes.

**Prerequisites:** Pinned dataset frame versions, Arrow conversion and assembly,
and Adapter capability preflight.

| title | breaking | description |
|---|---|---|
| Add CLI output-scope options | No | Add `--output`, `--head`, `--to`, and `--bind` to `uptimely run` with established validation modes. |
| Add equivalent Python run options | No | Expose equivalent options through `uptimely.run(...)`. |
| Prune plans to requested outputs | No | Define pruning from declared inputs and outputs and retain required producers. Writes within scope execute normally, including during validation. Do not add a separate write-authorization policy. |

## Work package: Runtime environments and preflight

Apply named environment configuration without mutating saved builds, and
validate execution requirements before workflow data I/O.

**Prerequisites:** Scoped run options and Adapter capability preflight.

| title | breaking | description |
|---|---|---|
| Add named runtime environments | No | Support named environments and deterministic layered configuration with clear missing-value errors. |
| Apply environment-specific runtime bindings | No | Use environment-specific parameters for write destinations, including non-production validation destinations. Reuse plans when only runtime bindings change. |
| Keep build artifacts immutable and secret-free | No | Record environment and non-sensitive provenance, exclude secrets from artifacts, and apply runtime overrides without mutating the published build. |
| Validate saved plans and runtime bindings in preflight | No | Check plan identity, output scope, runtime bindings, callable entrypoints, and backend compatibility before execution. |
| Keep preflight free of workflow execution | No | Reuse target-aware diagnostics without running analytical functions or performing workflow data I/O. Preflight does not verify external source availability or input data. |
| Add secret-aware runtime bindings | No | Resolve secrets from environment variables or a provider at runtime, report missing values, redact secrets and keep them out of build artifacts. |

## Work package: Contract validation modes

Separate mandatory engine safety checks from optional declared-data-contract
validation.

**Prerequisites:** Adapter capability preflight.

| title | breaking | description |
|---|---|---|
| Keep mandatory safety checks enabled | Yes | Always check preflight, returned representations, required columns, collisions, and dimension-key uniqueness. |
| Add named contract-validation modes | Yes | Add `--validate contracts` and matching named Python API modes. Check extended actual types and declared data contracts using native capabilities and configured materialization policy. |
| Reject unsupported validation modes | Yes | Fail explicitly for unknown or unsupported modes. Do not make unconditional Arrow copies. |

## Work package: Data quality rule execution

Check real data with explicit rules that produce no features and do not change
data. Quality checks complement contracts and do not prove formula correctness.

**Prerequisites:** Contract validation modes, Arrow conversion and assembly,
Scoped run options, and Runtime environments and preflight.

| title | breaking | description |
|---|---|---|
| Define validation declarations and bindings | No | Add a `validations` section with calculation-style bindings and project code under `validations/`, separate from `calculations/`. |
| Define validation results and severity | No | Allow validation functions to return a boolean or failing rows, where an empty frame passes. Errors fail the run under normal failure policy. Warnings report and continue. |
| Run validations within requested scope | No | Include writes as ordinary in-scope steps and use environment-configured destinations. Do not add write-only gating. |
| Add quality and combined validation modes | No | Add `--validate quality` and `--validate all`, with the latter including contract checks. |
| Show validation status in Explorer | No | Display validations as feature status badges, not calculation steps. |

## Work package: Null and missing-value semantics

Make null and NaN handling explicit across quality checks and representation
conversions.

**Prerequisites:** Data quality rule execution, Function representation and
type contracts.

| title | breaking | description |
|---|---|---|
| Add reusable null checks | No | Provide separate any-null and all-null-column checks with explicit empty-dataset behavior and configurable severity. Run only declared checks. |
| Define missing-value policy | No | Define dataset-level null/NaN allowance with feature-level overrides. Allowed nulls are not failures by default. |
| Preserve nulls and NaNs across adapters | No | Preserve null and NaN distinctly in conversions or reject unsupported conversions, such as arrays without null-validity information. Keep quality checks separate from assembly safety. |

## Work package: Validation reports

Publish bounded, redacted quality outcomes for users and automation.

**Prerequisites:** Data quality rule execution.

| title | breaking | description |
|---|---|---|
| Define validation report records | No | Record validation, dataset, severity, pass/fail, failing-row count, bounded sample, message, and run/build identity. |
| Export and present validation reports | No | Support `--report <path>`, a CLI summary, and the latest report in Explorer. Replace the previous report per run rather than retaining shared history. |
| Protect validation report data | No | Make sample capture explicit and redact sensitive data. |

## Work package: Analytics CI/CD workflow

Provide a reproducible development workflow using the public testing helpers in
[the automated testing release](release-16-automated-testing.md). Fixture cases,
worked-example tables, and pytest integration are planned there rather than
embedded in the production specification.

**Prerequisites:** Scoped run options, Runtime environments and preflight,
Data quality rule execution, Validation reports, and Optional pytest integration.
Existing repository tests continue to accompany every software release.

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Expose and reuse specification validators in user tests instead of duplicating validation logic. |
| Document testing levels | No | Explain unit tests, named operator cases, controlled workflow tests, custom real-data checks, and runtime `validations/`, with their respective project locations. |
| Separate fixture and production-data checks | No | Keep fixture execution separate from production-data evaluation and require explicit opt-in for side-effecting tests. |
| Add a runnable analytics CI pipeline | No | Validate the Spec, build the plan, run unit and fixture workflow tests with contract and quality checks, and publish build and validation reports. |
| Promote immutable builds through environments | No | Promote the same build with runtime configuration supplied separately. Keep production credentials and data checks outside fixture-based CI. |

## Work package: Plan optimization and bounded concurrency

Optimize a correct, scoped plan and execute genuinely independent work.

**Prerequisites:** Pinned dataset frame versions, Arrow conversion and assembly,
Adapter capability preflight, Scoped run options, Runtime environments and preflight,
Data quality rule execution for shared validation and failure semantics.

| title | breaking | description |
|---|---|---|
| Add scoped-plan optimization | No | Add configurable optimization that reuses output-scope pruning and avoids redundant assembly, conversion, and materialization. Keep logical plans backend-independent. |
| Preserve optimized execution semantics | No | Preserve declared dependencies, validations, and writes within scope. Keep backend-specific choices in target-aware planning. Retain safety checks when optimization is disabled and test optimized/unoptimized equivalence. |
| Schedule independent dataset work concurrently | No | Run independent work concurrently with global and per-adapter limits. Group lazy collection where supported, such as `pl.collect_all`. |
| Bound scheduler resource use | No | Account for library threading, memory, process startup, and serialization. Do not start one process per callable or size workers only from the widest stage. |
| Preserve dependency and failure ordering | No | Wait for input producers to succeed before consumers start. Preserve validation and failure propagation without special write skipping. Optimization and concurrency may ship separately. |
