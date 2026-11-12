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
| Define profile suites and named cases | No | Discover `tests/uptimely/interface_data/<profile_id>.md` or `.json` relative to the analytics project. Require one source per profile and reject duplicate formats, unknown resources, duplicate cases, and empty selections explicitly. Group named cases under each operator using `assembly.<operator_id>` and `cases.<case_id>`. Keep fixtures outside the production Spec. |
| Parse Markdown and equivalent JSON | No | Use `markdown-it-py` with table support and strict Pydantic models. Follow Spec vocabulary with `compute.args.<name>`, `compute.returns`, `merge.args.<name>`, and `merge.returns`. Support parameter overrides, structured arguments, expected exceptions, explicit dataframe schemas, comparison options, and feature selection for expanded invocations. Convert both formats into the same reusable JSON representation and publish its JSON Schema. Preserve source locations in diagnostics. |
| Verify fixture typing and demonstrate cases | No | Cover escaped pipes, quoted strings, explicit nulls, empty frames, all-null columns, malformed headings, and duplicate JSON keys. Reject ambiguous types rather than silently coercing values. Add representative cases under `examples/pump_analytics/tests/uptimely/interface_data/`, using real operators and grain keys. Document the hierarchy, typing rules, and equivalent JSON authoring. |

## Work package: Isolated operator fixture execution

Execute existing compiled bindings against explicit fixture data without running
upstream producers or replacing normal engine run artifacts.

**Prerequisites:** Markdown and JSON operator case definitions.

| title | breaking | description |
|---|---|---|
| Reuse runtime invocation execution | No | Add the smallest shared execution seam needed to seed isolated dataset and fragment state, invoke a selected binding, capture its result, and apply existing contract checks. Reuse runtime argument resolution, entrypoints, built-in and custom merge behavior, grain keys, and row-context handling. Preserve production execution semantics and require disambiguation when an operator expands into multiple matching invocations. |
| Resolve fixtures and assert outcomes | No | Load static arguments from the saved build, resolve runtime parameters with case overrides, and require explicit runtime dataframe fixtures. Never execute upstream readers to fill missing data. Support compute-only, merge-only, and combined cases, asserting compute and merge independently with explicit merge fixtures. Collect lazy results before comparison. Use Polars assertion helpers with strict defaults, explicit numeric tolerances and row-order options, expected exceptions, and bounded differences. |
| Enforce case isolation and document limits | No | Start each case with fresh runtime state, continue independent cases after failures, and leave `_generated/run/` unchanged. Require explicit external-I/O opt-in for read, write, and escape bindings, without claiming to sandbox trusted Python functions. Verify missing fixtures, invalid overrides, lazy failures, merge contracts, and unchanged production behavior. Document how binding tests differ from chained operator and workflow tests. |

## Work package: Test CLI, saved reports, and Spec coverage

Expose sequential test execution and a persistent report contract usable by
automation, pytest, and Explorer.

**Prerequisites:** Isolated operator fixture execution.

| title | breaking | description |
|---|---|---|
| Add `uptimely test` | No | Follow existing project-root, configuration, and logging conventions. Default to interface fixtures. Support `--build`, profile/operator/case filters, and explicit external-I/O opt-in. Require a valid saved build even for literal-only cases. Exit 0 for a successful nonempty run, 1 for assertion or user-function failures, and 2 for invalid setup or no selected cases. Add installed-CLI and example-project tests and document the public Python runner. |
| Save normalized suites and results | No | Atomically publish the latest `_generated/tests/test.json` containing normalized Markdown/JSON suite data, source provenance, run ID and UTC timestamps, build identity and scope, case and assertion counts by profile, statuses, durations, bounded differences, and preparation diagnostics. Mark interrupted attempts incomplete, retain available failure diagnostics, and never write success-shaped fallback reports. Exclude secrets and unrestricted actual datasets. |
| Report explicit Spec coverage | No | Count profiles, operators, compute/merge bindings, and output features against clearly identified saved-build denominators. Separate declared, selected, executed, and passing coverage, preserve denominators when filtering, list uncovered IDs, and explain scoped builds and excluded side-effecting operators. Keep this distinct from Python statement coverage. Verify report contents, exit codes, failed runs, and case-versus-assertion totals directly. |

## Work package: Parallel fixture cases

Run independent cases concurrently without requiring pytest or changing engine
workflow scheduling.

**Prerequisites:** Test CLI, saved reports, and Spec coverage.

| title | breaking | description |
|---|---|---|
| Add process-isolated case workers | No | Add `--workers N`, defaulting to 1, with each complete case as the scheduling unit. Pass serialized case data and read-only build context rather than live frames. Keep one coordinator responsible for deterministic result ordering and final report publication. Respect library threading and resource limits, and document that external services and files are not isolated by process workers. |
| Verify parallel outcomes and failures | No | Test sequential/parallel equivalence, fresh case state, worker failures, interruption, and coordinator-owned reporting. Do not make this package depend on the planned engine parallel scheduler. |

## Work package: Explorer test reports

Make saved test outcomes inspectable in the live Explorer and static exports
without executing test code while serving.

**Prerequisites:** Test CLI, saved reports, and Spec coverage, plus the existing Explorer
frontend, FastAPI server, and static export.

| title | breaking | description |
|---|---|---|
| Serve validated saved reports | No | Read the current project's `_generated/tests/test.json` through a read-only FastAPI API. Validate report versions, distinguish absent and malformed reports, and detect stale build identities. Do not accept arbitrary filesystem paths, import test functions, or execute checks from report endpoints. |
| Add the Tests navigation section | No | Show run time, outcome, duration, profile counts, coverage, uncovered resources, and operator/case drill-down. Display compute and merge statuses, inputs, expected values, bounded actual values, schemas, and source references. Escape fixture and error text. Distinguish no-report, failed, incomplete, and stale-report states. |
| Preserve static exports and verify presentation | No | Include a validated test snapshot in Explorer exports, with an explicit not-run state when absent. Add focused API and existing-style Node frontend tests for counts, filters, tables, errors, stale reports, and API-free exports. Keep Explorer documentation minimal and update the CLI, Python API, project layout, and example guides. |

## Work package: Optional pytest integration

Adapt the shared runner to pytest without making pytest a requirement for
`uptimely test`.

**Prerequisites:** Test CLI, saved reports, and Spec coverage.

| title | breaking | description |
|---|---|---|
| Expose stable pytest collection | No | Offer an optional testing extra and collection helpers or an explicitly enabled plugin. Collect each named case as a separate pytest item with a stable identity and reuse the CLI runner's assertions and diagnostics. Prefer collection-time integration over a `to_pytest()` call that hides multiple cases inside one item. Keep pytest imports out of the core runner. |
| Support controlled workflow and validation tests | No | Provide project fixtures and controlled workflow execution, reusing available contract and quality checks rather than copying their logic. Include writes only when explicitly selected with test-environment destinations. Allow existing runtime quality validations to become individual pytest items when that capability is available, without blocking basic operator-case collection on it. |
| Coordinate reporting and document CI use | No | Keep the controller responsible for the combined report under pytest-xdist, provided as a separate optional dependency. Verify CLI/pytest agreement and individual case collection. Document ordinary Python unit tests, optional property/metamorphic tests, and controlled workflow tests alongside the fixture format. |

## Work package: Custom real-data quality tests

Let project code assert properties of fully evaluated profile datasets rather
than limiting quality testing to a fixed rule language or preview samples.

**Prerequisites:** Test CLI, saved reports, and Spec coverage.

| title | breaking | description |
|---|---|---|
| Define profile and feature quality checks | No | Discover explicitly registered Python checks under `tests/uptimely/quality/`. Provide a typed context with profile ID, grain and feature metadata, a fully collected dataset, and other explicitly requested datasets for cross-profile checks. Attribute outcomes to profiles and declared features without silently projecting the input frame. Keep these tests distinct from the runtime `validations` section in Data quality validations. |
| Evaluate real data explicitly | No | Add an explicit quality mode such as `uptimely test --kind quality --build`. Evaluate requested profile outputs using the active build and runtime configuration, collecting each required lazy dataset once. Keep checks isolated against mutation and mark evaluation failures as errors or blocked checks. Never use bounded run previews as full data or silently fall back to sampling. Fail explicitly when full evaluation exceeds resources. |
| Bound scope and share outcome reporting | No | Select profile outputs without downstream sinks by default and require explicit opt-in for side-effecting writes or opaque external workflows. This test command does not change `uptimely run` or runtime validation write semantics. Record evaluation scope, timestamps, row counts, check outcomes, and bounded diagnostic samples in the shared test report. Reuse shared validation result metadata where applicable rather than introducing competing quality-rule definitions. |
| Demonstrate quality testing levels | No | Add focused checks and examples for key uniqueness, required observations, null fractions, ranges, freshness, cross-profile reconciliation, and domain invariants. Keep domain thresholds in project code. Verify that checks receive complete datasets, evaluation occurs once, and source failures cannot pass. Document credential handling and keep production-data checks separate from fixture CI. |
