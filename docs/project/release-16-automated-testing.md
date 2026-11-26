# Release 16: Markdown and JSON test cases, reports, and Explorer test views

This is a planned release grouping, not a published software version. Work
packages remain ordered by their stated prerequisites and are sized for separate
pull requests.

Provide `uptimely test` and the public `uptimely.testing` package. Keep operator
fixture tests separate from runtime contract validation and real-data quality
checks, while sharing result reporting and Explorer presentation. The initial
implementation uses the existing Polars backend and does not require the planned
adapter redesign, engine scheduler, or Explorer package separation.

## Work package: Markdown and JSON operator case definitions

Define one strict, versioned test schema with equivalent Markdown and JSON
authoring formats. Named cases are required so each operator can cover normal,
empty, null, and error scenarios independently.

**Prerequisites:** Existing Spec compute and merge bindings and saved execution
plans.

| title | breaking | description |
|---|---|---|
| Discover profile suites and named cases | No | Load `tests/interface_data/<profile_id>.md` or `.json` relative to the project. Require one source per profile and reject duplicate formats, unknown resources, duplicate cases, and empty selections. |
| Group cases by operator | No | Use `assembly.<operator_id>` and `cases.<case_id>`. Keep fixtures outside the production Spec. |
| Parse Markdown tables strictly | No | Use `markdown-it-py` with table support and strict Pydantic models. Preserve source locations in diagnostics. |
| Define operator case fields | No | Support compute/merge arguments and returns, parameter overrides, structured arguments, expected exceptions, dataframe schemas, comparison options, and feature selection. |
| Normalize Markdown and JSON suites | No | Convert both authoring formats to the same reusable JSON representation and publish its JSON Schema. |
| Verify fixture parsing and typing | No | Cover escaped pipes, quoted strings, nulls, empty frames, all-null columns, malformed headings, and duplicate JSON keys. Reject ambiguous types instead of coercing. |
| Add and document representative cases | No | Add example cases using real operators and grain keys. Document case hierarchy, typing rules, and equivalent JSON authoring. |

## Work package: Isolated binding execution

Execute existing compiled bindings against explicit fixture data without running
upstream producers or replacing normal engine run artifacts.

**Prerequisites:** Markdown and JSON operator case definitions.

| title | breaking | description |
|---|---|---|
| Reuse merge and contract behavior | No | Apply existing contract checks and built-in/custom merge behavior. Require disambiguation when an operator matches multiple invocations. |

## Work package: Fixture arguments and assertions

Resolve explicit case inputs and compare compute and merge outcomes.

**Prerequisites:** Isolated binding execution.

| title | breaking | description |
|---|---|---|
| Resolve fixture arguments | No | Load static arguments from the saved build and runtime parameters with case overrides. Require explicit runtime dataframe fixtures. |
| Run compute and merge cases independently | No | Support compute-only, merge-only, and combined cases with explicit merge fixtures. Never execute upstream readers to fill missing fixture data. |
| Compare case outcomes | No | Collect lazy results before comparison. Use Polars assertion helpers with strict defaults, explicit tolerances and row-order options, expected exceptions, and bounded differences. |

## Work package: Case isolation and I/O controls

Keep fixture execution separate from normal runs and make external I/O opt-in.

**Prerequisites:** Fixture arguments and assertions.

| title | breaking | description |
|---|---|---|
| Gate external I/O and document trust limits | No | Require explicit opt-in for source reads, publication writes, and opaque workflows called through compute. Do not claim to sandbox trusted Python functions. |
| Verify fixture execution behavior | No | Test missing fixtures, invalid overrides, lazy failures, merge contracts, and unchanged production behavior. Document binding, chained-operator, and workflow test distinctions. |

## Work package: Test CLI and saved reports

Expose fixture execution through the CLI and publish a persistent report for
automation, pytest, and Explorer.

**Prerequisites:** Case isolation and I/O controls.

| title | breaking | description |
|---|---|---|
| Add the `uptimely test` command | No | Follow project-root, configuration, and logging conventions. Default to interface fixtures and support build, profile/operator/case filters, and explicit external-I/O opt-in. |
| Define test command exit behavior | No | Require a valid saved build. Return 0 for successful nonempty runs, 1 for assertion/user-function failures, and 2 for invalid setup or no selected cases. |
| Verify and document test invocation | No | Test the installed CLI and example project. Document the public Python runner. |
| Save normalized suites and provenance | No | Atomically write `artifacts/tests/test.json` with normalized suite data, source provenance, run ID, UTC timestamps, and build identity/scope. |
| Save case outcomes and diagnostics | No | Record case/assertion counts, statuses, durations, bounded differences, and preparation diagnostics. Mark interrupted runs incomplete and retain available failures. |
| Prevent unsafe fallback reports | No | Never write success-shaped fallback reports. Exclude secrets and unrestricted actual datasets. |

## Work package: Spec coverage reports

Report selected and executed test coverage against the saved build.

**Prerequisites:** Test CLI and saved reports.

| title | breaking | description |
|---|---|---|
| Define saved-build coverage denominators | No | Count profiles, operators, compute/merge bindings, and output features against identified saved-build denominators. |
| Report coverage states and uncovered resources | No | Distinguish declared, selected, executed, and passing coverage. Preserve denominators under filters and list uncovered IDs. |
| Explain coverage scope and verify reports | No | Explain scoped builds, excluded side-effecting operators, and how Spec coverage differs from Python statement coverage. Verify report content, exit codes, failures, and case/assertion totals. |

## Work package: Parallel fixture cases

Run independent cases concurrently without requiring pytest or changing engine
workflow scheduling.

**Prerequisites:** Test CLI and saved reports.

| title | breaking | description |
|---|---|---|
| Add configurable case workers | No | Add `--workers N`, defaulting to one, with each complete case as the scheduling unit. |
| Serialize case inputs for workers | No | Pass serialized case data and read-only build context rather than live frames. |
| Coordinate deterministic case reports | No | Keep one coordinator responsible for deterministic result order and final report publication. |
| Bound worker resources and state limitations | No | Respect library threading and resource limits. Document that process workers do not isolate external services or files. |
| Verify parallel case behavior | No | Test sequential/parallel equivalence, fresh case state, worker failures, interruption, and coordinator-owned reports. Do not depend on the engine parallel scheduler. |

## Work package: Saved test report API

Serve validated saved results without executing test code while handling
requests.

**Prerequisites:** Test CLI and saved reports.

| title | breaking | description |
|---|---|---|
| Detect stale build reports safely | No | Detect stale build identity. Do not accept arbitrary paths, import test functions, or execute checks from report endpoints. |

## Work package: Explorer test results

Make saved test outcomes inspectable in live Explorer and static exports.

**Prerequisites:** Saved test report API, Spec coverage reports, and existing Explorer
frontend, FastAPI server, and static export.

| title | breaking | description |
|---|---|---|
| Add the Explorer Tests section | No | Show run time, outcome, duration, profile counts, coverage, uncovered resources, and operator/case drill-down. |
| Show case inputs and results | No | Display compute/merge statuses, inputs, expected and bounded actual values, schemas, and source references. Escape fixture and error text. |
| Distinguish report states | No | Distinguish absent, failed, incomplete, and stale reports. |
| Test Explorer report presentation | No | Test API and frontend counts, filters, tables, errors, stale reports, and API-free exports. |
| Update test workflow documentation | No | Keep Explorer docs minimal and update CLI, Python API, project layout, and example guides. |

## Work package: Optional pytest integration

Adapt the shared runner to pytest without making pytest a requirement for
`uptimely test`.

**Prerequisites:** Test CLI and saved reports, Spec coverage reports.

| title | breaking | description |
|---|---|---|
| Add optional pytest integration | No | Provide an optional testing extra and collection helpers or an explicitly enabled plugin. Keep pytest imports out of the core runner. |
| Collect each named case as a pytest item | No | Give each item a stable identity and reuse CLI assertions and diagnostics. Prefer collection-time integration over a `to_pytest()` call that hides cases. |
| Add controlled workflow tests | No | Provide project fixtures and controlled execution. Reuse contract and quality checks. Include writes only when explicitly selected with test destinations. |
| Collect runtime quality validations | No | Allow runtime quality validations to become individual pytest items when available, without blocking operator-case collection. |
| Coordinate pytest reports | No | Keep the controller responsible for combined reports under optional pytest-xdist. |
| Verify pytest integration and document CI | No | Verify CLI/pytest agreement and case collection. Document unit, optional property/metamorphic, and controlled workflow tests. |

## Work package: Quality-check registration and context

Register project checks and define their context for evaluating profile data.

**Prerequisites:** Test CLI and saved reports.

| title | breaking | description |
|---|---|---|
| Discover registered Python quality checks | No | Load explicitly registered checks under `tests/quality/`. Keep these separate from runtime `validations`. |
| Define quality-check context | No | Provide profile ID, grain and feature metadata, a fully collected dataset, and explicitly requested datasets for cross-profile checks. |
| Attribute quality outcomes without projection | No | Attribute outcomes to profiles and declared features without silently projecting the input frame. |

## Work package: Full-data quality evaluation

Evaluate requested profile outputs completely and constrain side effects.

**Prerequisites:** Quality-check registration and context.

| title | breaking | description |
|---|---|---|
| Add explicit real-data test mode | No | Add a mode such as `uptimely test --kind quality --build` using the active build and runtime configuration. |
| Evaluate requested profile datasets once | No | Collect each required lazy dataset once. Mark evaluation failures as errors or blocked checks. |
| Keep quality checks isolated and complete | No | Prevent checks from mutating inputs. Never use previews as full data or silently sample. Fail when full evaluation exceeds resources. |
| Bound side-effecting quality scope | No | Exclude downstream sinks by default and require opt-in for writes or opaque external workflows. Do not change `uptimely run` or runtime validation write semantics. |

## Work package: Quality outcomes and examples

Share real-data check results and document useful testing patterns.

**Prerequisites:** Full-data quality evaluation.

| title | breaking | description |
|---|---|---|
| Save quality outcomes in shared reports | No | Record evaluation scope, timestamps, row counts, outcomes, and bounded samples. Reuse shared validation metadata where applicable. |
| Demonstrate quality testing levels | No | Add examples for uniqueness, required observations, null fractions, ranges, freshness, reconciliation, and domain invariants. Keep thresholds in project code. |
| Verify and document real-data checks | No | Verify complete datasets, single evaluation, and source failures. Document credentials and keep production-data checks separate from fixture CI. |
