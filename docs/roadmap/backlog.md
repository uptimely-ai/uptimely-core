# Backlog

Work packages are listed in dependency order. Each package names its
prerequisites; unrelated packages can proceed at the same time.
High-priority packages appear first within their dependency constraints.
Other independently scheduled work packages are listed at the end.

Version numbers are assigned when software releases are published. The
*breaking* column marks changes that require users to update their
specifications, projects, functions or commands.

## Work package: Explorer navigation and contextual controls

Separate resource lookup from dependency exploration without replacing the
traditional navigation shell. Keep Plan and Run mostly unchanged.

**Priority:** High.

**Prerequisites:** Existing Explorer catalogs, client-side navigation, and
static presentation snapshots.

| title | breaking | description |
|---|---|---|
| Separate Catalog and Lineage navigation | No | Rename Analytical model to Catalog for declaration browsing. Give Lineage its own section, initially containing the existing feature-lineage page, with Overview and Matrix added by later packages. Keep existing profile cards in Catalog rather than creating another equivalent card overview. Preserve resource direct links and browser history when reorganizing navigation. |
| Share resource details and exploration entry points | No | Reuse resource-detail content across Catalog and Lineage instead of maintaining competing descriptions. Link graph selections to their Catalog resources and add Explore dependencies entry points for profiles and features. Keep functions and dimensions directly searchable and browsable without graph navigation. |
| Separate view options from selection context | No | Use page-specific toolbars for search, scope, and display settings. Keep the active graph scope and fit/zoom controls visible on mobile. Put less frequent settings and legends under Options, separate from selected-resource actions and details. Replace the graph selection dialog on mobile with a compact, expandable bottom sheet with explicit close and expand controls. Do not stack Options and selection overlays. Preserve other pages' contextual navigation. |
| Verify navigation and mobile interaction | No | Test direct links, browser back/forward, keyboard navigation, selection details, overlay dismissal, narrow-screen layouts, and existing Plan and Run behavior. Page and focus changes belong in navigation history, while zoom, legend visibility, and transient graph selections do not create history entries. Update the Explorer guide for the new sections and contextual controls. |

## Work package: Focused feature lineage

Make feature search and bounded neighborhood exploration the base behavior,
with the full 2D/3D graph available as an explicit overview.

**Priority:** High.

**Prerequisites:** Explorer navigation and contextual controls.

| title | breaking | description |
|---|---|---|
| Define browser graph-query semantics | No | Keep Python build responsible for resolved, validated feature/operator dependencies, stable IDs, and metadata. Build incoming/outgoing adjacency indexes once in JavaScript and reuse them for interactive queries. Keep FastAPI serving snapshots without recompiling on interaction. Define root IDs, direction, feature-dependency depth, and node budget independently of operator visibility. Keep execution build scope distinct from Explorer view scope. Preserve static-export behavior without requiring a Python server. |
| Add focused neighborhoods and progressive expansion | No | Search for a feature and display its immediate inputs and consumers by default. Remove unrelated nodes from the layout rather than merely dimming them. Offer upstream/downstream expansion and explicit full ancestry or impact actions. Show boundary counts and distinguish hidden dependencies, budget-limited results, and genuinely absent connections. Apply operator visibility as a display projection without changing scope semantics. |
| Persist focus and validate scale | No | Persist focus, direction, and expansion scope in URLs and restore them through history. Test cross-profile traversal, shared producers, operator show/hide equivalence, isolated features, bounded results, and static exports. Measure snapshot size, memory, query latency, and visible-graph layout time on larger fixtures. Use a Web Worker if query work blocks interaction, but defer server queries or graph chunking until measurements justify them. Document the supported scope and any measured limits. |

## Work package: Profile lineage overview and drill-down

Add a dependency overview rather than duplicating the Catalog profile cards.
Use dedicated profile focus as the main drill-down mode, especially on mobile.

**Priority:** High.

**Prerequisites:** Focused feature lineage.

| title | breaking | description |
|---|---|---|
| Summarize direct profile dependencies | No | Add Lineage Overview with one collapsed node per profile and aggregated direct cross-profile feature dependencies. Retain the underlying feature relationships for inspection. Explain that profile aggregation can show apparent cycles even when feature lineage is acyclic and must not be interpreted as an execution DAG. |
| Add profile focus with external boundaries | No | Open a scoped profile view showing internal features/operators and compact external boundary nodes or ports. Identify relevant input and consumer features, provide boundary counts, and allow users to inspect or focus a neighboring profile. Offer feature-neighborhood focus from the same view, with breadcrumbs, direct links, and a clear return to the previous scope. Make Focus profile the primary mobile action. |
| Support bounded in-place expansion | No | Allow a few profiles to expand together in the overview, with named external ports and only connections relevant to their displayed contents. Keep expansion distinct from navigation to a focused profile. Preserve selection on collapse and avoid unnecessary layout movement. Apply explicit visibility budgets rather than recreating the full graph accidentally. |
| Verify overview and drill-down | No | Test aggregate-edge provenance, cross-profile connections, apparent profile cycles, expand/collapse, focus history, stable selection, mobile boundaries, and static exports. Update the Explorer guide to distinguish Catalog cards, dependency overview, in-place expansion, and focused drill-down. |

## Work package: Source-to-target lineage tracing

Improve existing lineage highlighting with an explicit, narrowly scoped
source-to-target exploration workflow rather than duplicating it.

**Priority:** High.

**Prerequisites:** Focused feature lineage.

| title | breaking | description |
|---|---|---|
| Add explicit source and target selection | No | Reuse existing graph selection and highlighting to choose a source and target. Display only nodes and edges on directed paths between them, preserving branches and producing operators. Distinguish the complete path corridor from any simplified representative path and report disconnected endpoints or budget-limited results explicitly. |
| Verify path scope and navigation | No | Test branching, shared intermediates, cross-profile paths, identical endpoints, disconnected selections, operator visibility, and bounded output. Persist endpoints in direct links and history, support mobile endpoint selection, and document how tracing differs from full ancestry and downstream impact. |

## Work package: Profile dependency matrix

Add a compact coupling view that opens the same focused lineage workflow.
Nested feature-level matrices are outside this initial package.

**Priority:** High.

**Prerequisites:** Profile lineage overview and drill-down.

| title | breaking | description |
|---|---|---|
| Add the profile dependency matrix | No | Add Lineage Matrix with supplying profiles as rows and consuming profiles as columns. Count distinct direct feature-to-feature dependency pairs across each profile boundary, collapsing operators and deduplicating repeated pairs. Label the count definition and treat within-profile dependencies separately. Provide search, deterministic ordering, and virtualization when needed rather than relying on color alone. |
| Connect matrix selections to focused lineage | No | Selecting a cell lists its exact source/target feature pairs and offers Explore these dependencies. Row and column actions show profile consumers and suppliers. Reuse profile focus and resource details, with mobile-friendly cell inspection and accessible non-visual dependency lists. |
| Distinguish direct dependencies from reachability | No | Offer a clearly labeled reachability mode separately from direct-pair counts. Derive reachability from actual feature paths rather than paths through the collapsed profile graph, which can imply connections that do not exist. |
| Verify matrix semantics and usability | No | Test direction labels, deduplication, cell provenance, empty cells, apparent profile cycles, reachability, ordering, focused-lineage links, keyboard access, mobile scrolling, and static exports. Document how the matrix answers coupling questions rather than execution order or run status. |


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

## Work package: Testing and CI/CD

Provide public testing helpers and a reproducible development workflow.

**Prerequisites:** Runtime configuration and scoped execution; Data quality
validations. Existing repository tests continue to accompany every software
release.

| title | breaking | description |
|---|---|---|
| Reuse specification validation functions | No | Expose and reuse specification validators in user tests instead of duplicating validation logic. |
| Add the `uptimely.testing` pytest plugin | No | Provide a project fixture, workflow execution on fixture data with all validations and assertions showing failing rows. Include writes using test-environment destinations rather than automatically skipping them. Allow each data-quality validation to be collected as a separate pytest item in CI/CD. |
| Add worked examples | No | Store small input/output tables per function in the specification. Explorer shows before-and-after tables and the pytest plugin executes them as tests. |
| Document testing levels | No | Explain unit tests, worked examples, workflow tests on fixtures and real-data validations in the project structure guide, with `tests/unit/`, `tests/workflow/`, `tests/fixtures/` and `validations/` folders. |
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

## Work package: Additional dataframe adapters

Extend supported libraries without conflating interchange with native assembly.

**Prerequisites:** Frame adapter contracts and their conformance suites.
Parallel scheduling is not required for an adapter to ship.

| title | breaking | description |
|---|---|---|
| Add conversion adapters and native implementations as needed | No | Start with pandas interchange and add DuckDB and PyArrow support for concrete workflows. Document capabilities and run the applicable conformance suites; conversion does not imply native assembly. Polars remains the default. NumPy and PyTorch can be used inside function bodies without requiring tensor feature support. |
| Add a mixed-library dataframe example | No | Demonstrate user-written conversion decorators, explicit module loading and Polars assembly of foreign fragments. Show native pass-through, conversions, unsupported types and actionable missing-capability errors. |
| Show conversion and assembly points in Explorer | No | Display known representation changes, selected assembly implementations and materialization requirements. Mark unresolved boundaries explicitly rather than claiming the portable compiler can infer every conversion. |


| title | breaking | description |
|---|---|---|
| Add explanations for non-experts | No | Extend metadata extraction with `Explanation:` and `Formula:` sections containing argument placeholders. Explorer fills them with bound feature descriptions and units and combines them into output lineage stories. |

## Work package: Freshness-aware scheduling

Derive schedules from declared result freshness without changing the meaning
of analytical dependencies.

**Prerequisites:** Pinned dataset frame versions; Runtime configuration and
scoped execution. Parallel execution is not required.

| title | breaking | description |
|---|---|---|
| Add freshness to the specification | No | Define freshness requirements for mappings or features, their propagation through declared input/output dependencies and how external source availability constrains achievable schedules. Specify schedule-multiple and compatibility rules without introducing separate side-effect dependencies. Reject incompatible requirements with actionable diagnostics. Add derived schedules only after these semantics are defined; earlier work packages validate existing schedule declarations only. |

## Work package: Example extensions

Consolidate and extend runnable analytics examples, not migration work deferred
from earlier work packages.

**Prerequisites:** The callable contracts and operator bindings used by each example.

| title | breaking | description |
|---|---|---|
| Add signal processing to `pump_analytics` | No | Add NumPy-based signal processing and sliding-window calculations with meaningful aggregation and bounded windows. |

## Work package: Distributed dataframe adapters

Add remote-native execution only for workflows that need it, after local
contracts, configuration, tests and diagnostics are established.

**Prerequisites:** Frame adapter contracts and conformance suites;
Runtime configuration and scoped execution; Testing and CI/CD;
Execution reports and inspection for report export, not its Explorer view.

| title | breaking | description |
|---|---|---|
| Add PySpark and Snowpark native execution support | No | Support cluster-native inspection, validation and assembly; Arrow conversion alone is not distributed execution. Keep frames and joins remote on native paths. Show remote-to-local transfer in the plan and require explicit permission, such as `uptimely run --allow-remote-transfer`, with transfer limits. Missing native capabilities must not implicitly collect into Polars. Test remote failure and transfer diagnostics and expose them in execution reports. |

## Independently scheduled work packages and extensions

These are not blocked by the full preferred sequence above. Ship when their
specific prerequisites and user needs justify them.

### Specification summary

**Prerequisites:** Existing specification model.

| title | breaking | description |
|---|---|---|
| Print a concise spec summary | No | Add a public `Spec.print_summary()` method that prints a readable overview of a specification, and demonstrate it in the project README's Python example. |

### Polars 2.0 upgrade

**Prerequisites:** An available upstream software release and successful compatibility
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

## Work package: Reproducible builds and diagnostics

Make builds identifiable and immutable, and source-loading failures actionable.

**Prerequisites:** No new execution capability; provenance records must evolve
with changes to specification and plan formats.

| title | breaking | description |
|---|---|---|
| Record execution requirements | No | Record callable module references, declared package requirements and available version provenance in the build manifest. Provide checks for requirement availability and compatibility without executing analytical functions, for reuse by strict target-aware compilation and engine preflight. Distinguish declared requirements from best-effort import analysis; dynamic imports cannot be exhaustively inferred. Do not install dependencies automatically. |
| Preserve immutable build snapshots | No | Published artifacts retain fixed specification, mapping bindings, plan and callable implementation source with stable build identity. Package callable code in the bundle as a wheel for packaged projects or a source archive for supported pure-Python projects; record its content hash and load implementations from that artifact at runtime rather than mutable project files. An import path or source fingerprint alone does not freeze implementation. Record dependency requirements and provenance separately; bundling project source does not bundle third-party dependencies. Changed logic or bindings require a new build, not a new authoring identity for every function or mapping. Runtime overrides must not mutate published artifacts. |
| Improve build-source diagnostics | No | Distinguish malformed `module:attribute` entrypoints, missing spec sources and import failures inside otherwise valid modules. Preserve the underlying exception cause and actionable message, and offer a verbose traceback option. Cover Python and JSON source selection, project-directory discovery and nested import failures in tests; document the current CLI syntax rather than introducing a duplicate project-directory option. |
| Align examples with the documented project layout | Maybe | Link example READMEs to the project structure guide and keep specifications in `spec/`, separate from runtime configuration. Align examples and documentation around importable implementation packages, using a `src/` layout where packaging is needed and grouping I/O and calculations consistently. Add validation folders when quality validations ship. Keep deployment assets separate from analytical functions; automatic assembly needs no user-authored merge category. Update scaffolding, entrypoints, commands and tests together. Breaking changes in earlier work packages must still migrate affected examples immediately. |

## Isolated runtime execution plan

The following work packages implement one design in stages. This is a proposed
layout and behavior, not a description of currently supported execution.

### Example project structure

```text
project/
├── pyproject.toml                     # Developer tooling dependencies
├── poetry.lock
├── runtimes/                          # Committed and bundled definitions
│   ├── cpu/
│   │   ├── runtime.json
│   │   ├── requirements.in            # Maintained Python dependencies
│   │   └── requirements.lock          # Locked installation input
│   └── pytorch_gpu/
│       ├── runtime.json
│       ├── requirements.in
│       ├── requirements.lock
│       └── Dockerfile                 # Alternatively a pinned image reference
├── functions/                         # Importable implementation modules
│   ├── cpu/
│   │   └── analytics.py
│   └── pytorch_gpu/
│       └── predict.py
├── spec/
│   └── spec.py                        # Deferred implementation references
├── config/
│   └── config.json                    # Runtime parameters and engine controls
├── deployment/                        # User-owned bundle submission functions
│   ├── local.py
│   └── prefect.py
├── data/
│   ├── input/
│   └── output/
├── .cache/                            # Ignored machine-local reusable state
│   └── uptimely/
│       └── runtimes/
│           └── <content-hash>/
│               └── venv/
└── _generated/                        # Generated artifacts, not installations
    ├── build/
    ├── bundles/
    │   └── <build-id>.zip
    └── run/
```

Python packaging must keep the function modules importable, adding package
markers or a packaged source layout as needed. The CPU/GPU split is illustrative,
not a requirement that every project use these runtime names or Docker.
Requirements files are Python-specific inputs, not fields imposed on other
languages by the runtime contract.

### Prerequisites and constraints

- Existing Spec JSON and deferred entrypoints provide the declaration starting
  point. Runtime declarations and explicit provisioning precede isolated
  inspection, which precedes portable bundle export and whole-graph launchers.
  Each work package below names its actual prerequisites.
- The developer's Poetry environment supplies authoring, compiler, driver, and
  deployment tooling only. Every Python worker runtime includes pinned Uptimely
  Core and its own dependencies. Non-Python workers implement the compatible
  protocol rather than installing the Python package.
- Use `runtime` for dependency stacks and worker requirements. Keep development,
  test, and production configuration environments separate. Runtime definitions
  declare capabilities, while deployment selects hosts, resources, and secrets.
- Provision through an explicit preparation or deployment action. Inspection
  needs an already prepared runtime unless portable contracts are supplied
  explicitly. Neither Spec loading nor compilation silently installs packages.
- Definitions and locks are portable inputs. Venvs are machine-local caches and
  never bundled. Cache deletion requires reprovisioning, not an analytical
  change. Docker images live in Docker storage. Offline use requires compatible
  dependencies or images supplied in addition to requirements.
- Select each function runtime's interpreter for editing and testing, using
  folder/project mappings when useful. Do not merge venv package paths. The
  editor does not select interpreters from Uptimely decorators automatically.
- Arrow IPC carries representable tabular values, not lazy execution plans or
  arbitrary Python objects. Control metadata and non-tabular artifact references
  use a separate portable protocol. Unsupported boundaries fail explicitly.

### Expected behavior and delivery phases

1. Author the Spec using deferred function references. Resolve the owning runtime
   from `functions/<runtime-id>/` before importing implementations, then check
   any `runtime="..."` decorator declaration for agreement. External packages
   need explicit runtime associations.
2. Inspect signatures, annotations, decorators, and documentation inside the
   owning runtime. Return portable contracts to the compiler. Inspection does
   not call analytical functions, but module-level code still runs in the
   worker. Apply this isolation to all implementation-inspection tools.
3. Compile and export immutable ZIP bundles with source, assets, Spec, plan,
   contracts, runtime definitions, dependency locks, and integrity metadata.
   Execution uses bundled implementations rather than mutable project files.
4. Initially deploy the entire graph as one isolated venv or Docker job.
   Reject graphs requiring multiple runtimes until segmented execution ships.
   User functions in `deployment/` submit bundles locally, through Prefect, or
   through other orchestrators without reproducing compiler scheduling.
5. Add compiler-selected segments, cutting flows at runtime changes or
   incompatible dataframe representations. Retain compatible native paths,
   materialize explicitly at Arrow IPC boundaries, and preserve merge,
   publication, and side-effect dependencies. Stages describe dependency
   levels, segments describe worker jobs, and partitions describe record
   subsets. These concepts are not interchangeable.
6. Evolve the engine from a whole-graph worker into a driver, first executing
   segments sequentially, then concurrently and across nodes. Publish only
   successful outputs and report failures and skipped dependents. Concurrency
   requires isolated state and bounded resources. Record partitioning and
   distributed-native dataframe execution remain separate capabilities.

## Work package: Function runtime declarations and project layout

Define isolated dependency stacks as runtimes, separate from development,
test, and production configuration environments.

**Prerequisites:** Existing Spec JSON, deferred function references, and
project layout.

| title | breaking | description |
|---|---|---|
| Define portable runtime declarations | Yes | Add language-neutral `runtimes/<id>/runtime.json` definitions with worker commands, protocol versions, dependency/build inputs, and required capabilities such as GPU support. Python targets reference dependency files and a Python version, while other languages can use their own ecosystem inputs. Keep host placement, credentials, and orchestration policy outside these definitions. Carry function runtime references through decorators, Python authoring, Spec JSON, and plans without making decorators mandatory. |
| Organize functions by runtime | Yes | Use `functions/<runtime-id>/` for implementations and `runtimes/<runtime-id>/` for their definitions. Discover the runtime from this mapping before importing a function, then validate any decorator runtime declaration against it. Require explicit associations for external implementation packages. Update project scaffolding, examples, entrypoints, and project structure documentation together. Avoid mixing incompatible runtime implementations in one Python module. |
| Separate runtime caches from generated outputs | No | Store reusable machine-local installations under project-root `.cache/uptimely/runtimes/<content-hash>/`, separate from `_generated/` build and run outputs. Ignore caches in version control and exclude them from bundles. Define cache identity from runtime and provisioning inputs, invalidation, and explicit cleanup. Docker images remain in Docker-managed storage. Test missing definitions, conflicting runtime references, and portable path validation. |

## Work package: Isolated Python runtime provisioning

Provision function dependencies without inheriting the developer's Poetry
environment.

**Prerequisites:** Function runtime declarations and project layout.

| title | breaking | description |
|---|---|---|
| Provision locked Python runtimes | No | Use uv as the default venv provisioner with a pip alternative consuming locked pip-compatible requirements. Support maintained dependency declarations and explicit lock generation, including transitive pins, hashes where supported, Python version, package indexes without credentials, and destination platform constraints. Provision only through an explicit preparation command or deployment request, not implicit compiler dependency installation. Report installation and compatibility failures explicitly. |
| Include the Uptimely worker in each runtime | No | Install a pinned compatible Uptimely Core worker dependency in every Python runtime, with explicit protocol and plan compatibility checks. Launch the runtime interpreter directly without developer-environment activation or inherited Python package search paths. Define how project implementation code is installed for development and later from immutable bundles. Do not require the Python package in non-Python runtimes, which must implement the compatible worker protocol. |
| Verify isolated development and installation | No | Test missing packages, conflicting dependency versions, stale caches, interpreter selection, and provisioning failures. Document editing functions with their runtime interpreter, using per-folder/project editor mappings where supported, and testing inside the actual runtime. Do not merge multiple venv `site-packages` or rely on a development superset for correctness. |

## Work package: Runtime-isolated function contract inspection

Load the Spec and compile portable contracts without importing analytical
implementations into the developer or compiler process.

**Prerequisites:** Isolated Python runtime provisioning.

| title | breaking | description |
|---|---|---|
| Extract contracts inside the owning runtime | Yes | Use deferred entrypoint references during Spec authoring. Batch inspection requests per runtime, import implementations inside that runtime, and return serializable argument names, logical types, required-argument information, return roles, decorator metadata, descriptions, and package provenance. Do not execute analytical functions during inspection or return live Python callables and type objects. Make import failures actionable and document that module-level initialization still runs. |
| Reuse extracted contracts across build tools | Yes | Replace compiler-local signature imports with runtime inspection results. Apply the same isolation to authoring conversion, documentation generation, and other implementation-inspection surfaces. Validate bindings against extracted contracts and cache results with source and runtime identity so changes cannot reuse stale metadata. Allow explicit portable contracts for non-Python implementations or compilation without runtime provisioning, with implementation compatibility checked before execution. |
| Verify build-time isolation | No | Add fixtures whose implementations require incompatible packages absent from the compiler environment. Verify Spec loading, inspection, compilation, and documentation without importing those packages into the parent process. Cover runtime discovery before decorator inspection, import side effects confined to workers, annotation resolution, explicit-contract drift, and cache invalidation. |

## Work package: Portable ZIP execution bundles

Extend immutable build snapshots into deployable artifacts containing code and
runtime requirements, not machine-local installations.

**Prerequisites:** Reproducible builds and diagnostics;
Runtime-isolated function contract inspection.

| title | breaking | description |
|---|---|---|
| Export versioned execution bundles | No | Package the saved Spec, execution plan, inspected contracts, implementation wheels or supported source archives, supporting assets, runtime definitions, dependency locks, and compatibility metadata in a ZIP with a versioned manifest and content hashes. Reuse immutable build identity and source packaging rather than creating a second snapshot mechanism. Use explicit inclusion rules and reject unsafe archive paths. Exclude secrets, venvs, caches, data, and diagnostics unless a supported asset is explicitly selected. |
| Define destination preparation and loading | No | Verify bundle integrity and protocol compatibility, extract safely, install implementations from the immutable artifact, and recreate runtime installations at the destination. Distinguish a source bundle requiring dependency installation or image pulls from offline deployment with separately supplied compatible wheels or images. Requirements alone do not guarantee offline execution or cross-platform compatibility. |
| Verify portable bundle execution inputs | No | Test round trips, missing and modified artifacts, source changes after export, archive traversal, excluded cache/secret files, destination platform mismatches, and explicit installation failures. Document bundle contents, reproducibility limits, and the difference between dependency requirements and bundled dependencies. |

## Work package: Whole-graph isolated runtime launchers

Initially launch the existing engine as one whole-graph worker job rather
than introducing distributed scheduling.

**Prerequisites:** Portable ZIP execution bundles.

| title | breaking | description |
|---|---|---|
| Launch a whole graph in a venv process | Yes | Run the bundled graph using its isolated runtime interpreter and bundled implementations, not mutable project modules or developer dependencies. Keep the parent process responsible for preparation and launch only. Until segmented execution ships, reject graphs requiring multiple runtimes explicitly. Preserve existing result, validation, failure, and diagnostic behavior. |
| Add a Docker launcher using the same job contract | No | Build from a declared Dockerfile or use a pinned image reference, then launch the same bundle job with explicit data access and resource configuration. Validate required capabilities, including GPU host-driver and container compatibility. Distinguish venv dependency isolation from OS/container isolation, and report unsupported placement without falling back to the developer process. |
| Verify launcher equivalence | No | Test process exit status, worker errors, output collection, immutable source loading, and local venv/Docker result equivalence on supported fixtures. Document provisioning commands, mounted input/output locations, resource requirements, and rebuilding after runtime changes. |

## Work package: Bundle deployment adapters

Keep deployment user-defined and independent of analytical declarations.

**Prerequisites:** Whole-graph isolated runtime launchers.

| title | breaking | description |
|---|---|---|
| Define a deployment submission contract | No | Place user-owned deployment functions in `deployment/`. Accept an immutable bundle plus destination configuration and return submission identity/status rather than assuming synchronous completion. Keep provisioning, placement, resources, secret injection, and orchestration policy here, outside the Spec. Surface submission and execution failures distinctly. |
| Demonstrate local and Prefect deployment | No | Provide local-process and Prefect examples that deploy the same whole-graph bundle, with a contract reusable by other orchestrators. Initially orchestrators launch one engine job rather than duplicating invocation scheduling. Test submission, status, and error propagation with adapter fixtures and document the extension pattern without requiring Prefect in every worker runtime. |

## Work package: Arrow IPC worker boundaries

Define a language-neutral worker interface separating tabular exchange from
execution control.

**Prerequisites:** Frame adapter contracts; Portable ZIP execution bundles.

| title | breaking | description |
|---|---|---|
| Define worker requests and tabular exchange | No | Use Arrow IPC for dataframe inputs and outputs across runtime and incompatible-representation boundaries. Define a separate versioned control envelope for execution, segment, and invocation IDs, scalar arguments, artifact references, schemas, grain keys, preservation requirements, statuses, and diagnostics. Keep transport separate from encoding so local files/pipes and later remote artifact stores can carry the same contract. |
| Implement and validate the Python worker protocol | No | Reuse adapter conversion contracts, retaining native frames within compatible work. Materialize at IPC boundaries explicitly, preserve declared key/order/type semantics, and reject unsupported Python objects or conversions. Keep non-tabular models and other artifacts behind explicit references rather than assuming arbitrary tensors are tabular IPC payloads. Test round trips, empty inputs, malformed messages, schema fidelity, and protocol mismatches, and document the non-Python worker contract. |

## Work package: Compiler execution segmentation

Identify compatible subgraphs and independent work without conflating
dependency levels with distributed data partitions.

**Prerequisites:** Arrow IPC worker boundaries.

| title | breaking | description |
|---|---|---|
| Compile execution segments and boundary contracts | Yes | Retain invocation dependencies and scheduling stages, and add separately identified execution segments. Cut flows at runtime changes and incompatible dataframe representations, recording Arrow IPC input/output contracts and materialization points. Group compatible work only when dependencies and preservation semantics permit it, preserving native lazy optimization. Leave unknown representation choices unresolved until target-aware planning and fail if execution cannot resolve them. |
| Preserve publication and side-effect dependencies | No | Record isolated computation outputs and explicit merge/publication dependencies rather than treating shared profile mutations as parallel-safe. Preserve declared side-effect ordering and report work whose concurrency safety is unknown. Distinguish independent invocations from record partitionability, which requires separate aggregation, window, and state contracts. Test branched graphs, joins, shared consumers, representation changes within one runtime, and runtime changes using the same representation. |
| Expose segmented plans | No | Update plan serialization, validation, diagnostics, and Explorer to distinguish stages, segments, and interchange boundaries. Verify stable segment references, complete dependency coverage, and equivalence to unsegmented execution for supported fixtures. Document that compiler-identified concurrency does not by itself provide multi-node execution. |

## Work package: Sequential cross-runtime graph execution

Run segmented graphs correctly before adding concurrent or remote scheduling.

**Prerequisites:** Compiler execution segmentation;
Whole-graph isolated runtime launchers.

| title | breaking | description |
|---|---|---|
| Execute segments through isolated workers | Yes | Extend the engine into a driver that sequentially submits ready segments through venv or Docker launchers, passes Arrow IPC artifacts, and publishes results only after successful completion. Load implementations only in their assigned runtime. Preserve merge contracts, validation, whole-graph outputs, per-invocation status, and explicit downstream skipping after failures. |
| Verify mixed-runtime execution and diagnostics | No | Add CPU and GPU-runtime configuration examples, with hardware-independent worker fixtures for routine tests and explicit hardware integration checks. Cover incompatible dependency versions, mixed dataframe representations, IPC failures, artifact lifetime/cleanup, worker startup failures, and result equivalence. Keep the single-runtime whole-graph path available and document the transition to driver execution. |

## Work package: Parallel and multi-node segment driving

Schedule compiler-identified segments across workers without duplicating
planning in deployment adapters.

**Prerequisites:** Sequential cross-runtime graph execution;
Plan optimization and bounded concurrency.

| title | breaking | description |
|---|---|---|
| Schedule independent segments concurrently | No | Extend the bounded scheduler to segment jobs with global and per-runtime resource limits, dependency-aware readiness, isolated outputs, and deterministic publication. Account for library threading, memory, transfer costs, and worker reuse rather than launching one process per callable. Verify sequential/concurrent equivalence and failure propagation, including side effects and shared profile consumers. |
| Add remote placement and lifecycle controls | No | Extend the driver/launcher contract to multi-node submission and Arrow IPC artifact references with explicit remote transfer limits. Keep placement in deployment configuration, and implement status reporting, cancellation, resource cleanup, and retry policy with idempotency requirements for side effects. Test remote failures and distinguish independent-segment distribution from future record partitioning or distributed-native dataframe adapters. Orchestrator adapters may submit segment jobs through this contract without rebuilding graph dependencies. |

## Work package: Executable scopes

Turn profile scope from descriptive text into reusable, executable row
selection while keeping resolution (row detail) distinct from scope (included
rows).

**Prerequisites:** Specification model migration; Frame adapter contracts.

For example, a profile can use asset/minute resolution while its scope selects
assets by product family and limits the measurement-time range. A reusable
scope can declare filters directly or compute them through an action. This
illustrative JSON uses the proposed profile terminology; exact reference
syntax is established by the specification-contract work above.

```json
{
  "dimensions": {
    "operating_unit": {
      "type": "hierarchy",
      "resolutions": ["fleet", "product_group", "asset"]
    },
    "measurement_time": {
      "type": "datetime",
      "resolutions": ["day", "hour", "minute"]
    }
  },
  "scopes": {
    "families_a_and_b": {
      "name": "Assets in product families A and B",
      "filters": {
        "product_family": {"in": ["A", "B"]},
        "measurement_timestamp": {
          "range": {
            "gte": "2026-01-01T00:00:00Z",
            "lt": "2026-02-01T00:00:00Z"
          }
        }
      }
    },
    "custom_north_scope": {
      "name": "Custom North operations scope",
      "action": {
        "function": "$functions.select_north_scope",
        "args": {}
      }
    }
  },
  "profiles": {
    "asset_minute": {
      "grain": [
        "$dimensions.operating_unit.resolutions.asset",
        "$dimensions.measurement_time.resolutions.minute"
      ],
      "scope": "$scopes.families_a_and_b"
    },
    "north_hourly": {
      "grain": [
        "$dimensions.operating_unit.resolutions.product_group",
        "$dimensions.measurement_time.resolutions.hour"
      ],
      "scope": "$scopes.custom_north_scope"
    }
  }
}
```

An action returns a `filters` mapping in the same form as the static scope.
For example, it could return `{"region": {"in": ["North"]}}`; it need not
enumerate every matching profile key. The filter column names and dimension
reference syntax above are illustrative, not a finalized schema contract.

The corresponding Python authoring API could use declarative `Scope` classes:

```python
class FamiliesAAndB(Scope):
    name = "Assets in product families A and B"
    filters = {
        "product_family": {"in": ["A", "B"]},
        "measurement_timestamp": {
            "range": {
                "gte": "2026-01-01T00:00:00Z",
                "lt": "2026-02-01T00:00:00Z",
            }
        },
    }


class CustomNorthScope(Scope):
    name = "Custom North operations scope"
    action = {
        "function": "functions.select_north_scope",
        "args": {},
    }
```

This class-based syntax is illustrative; the authoring contract should define
whether scope declarations are classes, instances, or both, and how action
references are expressed.

| title | breaking | description |
|---|---|---|
| Define reusable scope declarations and filter semantics | Yes | Replace descriptive profile scope text with references to reusable named scopes. Define each scope's `name` and exactly one of static `filters` or an `action`; define filter keys as dataset columns and the supported list and range forms, including empty selections, null handling, type compatibility, bound inclusivity, and how multiple filters combine. Define whether filters may refer to dimensions, features, or other columns, and how a scope can express custom reusable logic that is not a simple dimension/feature selection. Specify how a scope is interpreted at the profile's grain and resolution. |
| Validate and normalize static scope filters | No | Validate scope references, filter structure, column references, value types, range bounds, and operator semantics against profile schemas and grain. Normalize valid filters into a deterministic internal representation and report errors with scope, profile, column, and source-path context. Do not silently ignore unsupported or inapplicable filters. |
| Define and validate scope action contracts | No | Allow a scope to use an `action` bound to reusable project logic. Specify its arguments, dependencies, execution phase, purity and I/O expectations, and exact return contract. Require action-produced selections to use the same filter representation as static scopes, with an explicit extension point or diagnostic for custom selections that cannot be represented by lists or ranges. Validate bindings and return values without treating scope output as feature data or a dataframe fragment. |
| Compile scope dependencies and execution | No | Carry scope references, static filters, action bindings, and required inputs through compilation and portable plans. Schedule scope actions before every invocation that relies on their result, include dependencies in cycle and invocation validation, and keep scope execution distinct from feature-producing actions. Fail preflight on missing scope actions or unavailable required capabilities before workflow data I/O. |
| Apply scope consistently during execution | No | Apply resolved scope selections to profile observations at a defined engine boundary so all data-producing fragments and downstream calculations obey the same included-row semantics. Preserve eager/lazy behavior through the adapter contract, handle empty selections and range boundaries deterministically, and fail explicitly when a scope cannot be applied to a representation. Do not interpret descriptive text as executable or silently widen/narrow a scope. |
| Test, document, and migrate executable scopes | No | Add unit, integration, and adapter conformance coverage for static and action-produced scopes, list and range filters, independent time dimensions, hierarchical resolutions, empty results, invalid columns and types, lazy execution, and custom-scope limitations. Update authoring, Python, CLI, engine, Explorer, examples, generated artifacts, and migration documentation to distinguish resolution from included-row scope. |

## Work package: Themes

Provide reusable, domain-specific starting points for analytics projects.

**Prerequisites:** Stable specification, configuration, and function contracts.

| title | breaking | description |
|---|---|---|
| Add domain themes | No | Ship selectable, versioned template sets for supported domains, including starter specifications and runtime configuration plus reusable functions for common domain calculations. Let project-owned configuration and functions override theme defaults using documented precedence rules. Keep templates customizable and explicit: adopting a theme must not silently add data or run calculations the user did not select. Document included assumptions, dependencies, and extension points. |
