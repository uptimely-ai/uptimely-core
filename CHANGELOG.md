# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased]

### Added

- `Project` provides root-bound build and bundle-loading operations. Import it
  from `uptimely` and use `Project().build()` to build the current directory.
- `Engine` can be constructed without an explicit runtime configuration; it uses
  the default engine settings.
- Profiles can declare `relations` as additional dimension resolutions without
  changing their grain. Relation columns are retained during fragment assembly and
  shown in Explorer's profile schema rather than its feature catalog or lineage.

### Changed

- Move `resolve_path` onto `Project`, using its stored root for default paths
  while preserving explicitly supplied paths unchanged.
- Rename `project.build_project()` to `project.build()`. The project root is
  optional and defaults to the current working directory.
- Python authoring exposes `from uptimely import merge` and `merge.default()`;
  `default_merge()` remains available as a compatibility alias.

- Operator interfaces now contain only feature dependencies and outputs.
  Identifiers and relations stay in profile schema and assembly metadata;
  Python authoring no longer adds identifier outputs or infers key inputs.

- Profile `identifiers` and `identifier_types` describe grain members;
  `relations` describe links to other grains, and `keys` combines both.
  Datasets and fragments expose the same distinction relative to their own rows.
  Explorer labels identifiers **ID** and related-profile columns **Relation**.
- **Breaking (plan and merge APIs):** Plan version 13 replaces `target_grain_keys`
  and `fragment_identifiers` with `target_identifiers` and `fragment_keys`.
  The built-in merge uses `dataset_identifiers` and `key_columns` arguments.
  Rebuild bundles and Explorer snapshots from their source Specs.

- **Breaking (Spec, plans, and Python API):** Callable contracts now declare
  arguments and return roles independently of operator behavior. The function
  `kind` field and authoring argument are removed; callable categories are
  optional descriptive metadata, used to group functions in Explorer. Operator
  grain relationships, execution forms, and compute/merge roles are derived
  from Spec declarations, not function categories. A dataframe result without
  a merge is a complete target; fragments require an explicit merge such as
  `merge.default()`. Disabling signature inspection requires explicit `args`
  and `returns`. Spec version 8, plan version 12, and Explorer snapshot version
  3 replace their previous formats. Migrate each operator based on its bindings
  and target behavior, then rebuild bundles and Explorer snapshots; old
  serialized formats are rejected. Plan version 12 uses only
  `target_grain_keys` and `fragment_identifiers`, replacing their legacy
  aliases.
- **Breaking (spec and Python API):** Spec version 7 renames profile dataset
  argument selectors from `.dataframe` to `.dataset` and renames
  `DATAFRAME_SELECTOR` to `DATASET_SELECTOR`. Function argument types remain
  `dataframe`. Migrate version 6 bindings and rebuild generated plans and
  Explorer snapshots.
- Compiler now owns operator-to-invocation expansion, Spec dependency rules,
  feature selection, and schedule selection. **Breaking (compiler API):**
  `InvocationGraph` now accepts compiler-created nodes and dependency IDs rather
  than a Spec. The Python plan API now represents each execution stage with
  `plan.Stage`; serialized stages remain arrays of invocation IDs.
- Compiler-generated invocation IDs now use compact operator labels and stable
  fingerprints, with single dashes within labels and `--` before the hash.
  IDs are at most 36 characters and identify the function, profile, and
  operator independently of function kind.
- **Breaking (plans):** Plan version 8 moves inspected return annotations and
  entrypoint package provenance onto each invocation, removing the root
  `resources` field. Rebuild bundles from their source Specs; version 7 plans
  are not supported.
- **Breaking (plans and Python API):** Plan version 7 replaces invocation
  `dataset_id` with `profile_id`, without a legacy alias. Compiler graph nodes
  and Explorer lineage metadata likewise use profile fields; feature graph
  nodes no longer duplicate profile identity as dataset metadata. Datasets
  remain engine-owned runtime accumulators. Rebuild bundles from their source
  Specs to replace version 6 plans and adopt compact IDs throughout plans,
  run logs, and Explorer.
- **Breaking (Python authoring):** Renamed `row_context.dataset()` to
  `row_context.all_rows()` to describe its row-context behavior without implying
  a spec-level Dataset.
- **Breaking (spec Python API):** Renamed profile-reference and dataframe-input
  helpers, cached views, and validators to distinguish profile IDs from engine
  Datasets. The mapping-input validation error code is now
  `invalid_mapping_dataframe_input`.
- **Breaking:** Renamed `RuntimeState.main_frames` and
  `ExecutionResult.main_frames` to `datasets`. Values remain final dataframes
  keyed by dataset ID.
- **Breaking (Python imports):** Removed the `uptimely.execution_plan` and
  `uptimely.project_paths` forwarding modules. Import plan APIs from
  `uptimely.plan` and project paths from `uptimely.project.paths`.
- **Breaking (Python document models):** `Binding.args` now contains
  `BindingArgument` objects. Read raw values through `.root`, or serialize the
  binding with `model_dump()`. JSON remains unchanged. Bound arguments own
  reference resolution and inferred dependencies; model definitions now live
  in focused modules rather than `model.common`. Package-level model imports
  remain available. Python authoring also infers omitted interface inputs from
  bare feature-reference strings, while explicit inputs remain authoritative.
- **Breaking:** Vectorize functions now return the complete enriched target
  dataframe, preserving existing columns and adding declared outputs. They no
  longer return fragments that the engine joins into the target.
- **Breaking:** Spec version 6 adds explicit merge bindings and changes
  fragment assembly to scheduled merge invocations. Version 5 Specs and
  version 5 or older plans must be rebuilt from source; omitted fragment merge
  bindings resolve to the builtin default, while explicit bindings override it.
- **Breaking:** Spec version 5 uses `assembly` instead of `actions` in profiles,
  infers operator IDs from assembly keys, and renames the operator fields
  `binding` and `features` to `compute` and `interface`. Version 4 documents
  must be migrated and rebuilt; compatibility parsing is not provided.

## [0.9.0] - 2026-11-03

### Added

- Every engine execution now replaces `_generated/run/` with latest-run
  metadata, structured JSONL logs, invocation outcomes, and bounded profile
  previews, including partial results after failure. Previews collect lazy
  queries by default and report sampling errors separately. Explorer provides
  fresh read APIs for these artifacts, with run-ID consistency checks.
- Spec and compiler validation now emit debug traces with headings and
  indented check bullets, including reasons for skipped signature checks.
  Document structure checks summarize profile and action counts rather than
  repeating messages for every resource. Python conversion also summarizes
  action output-reference checks once instead of logging each repeated check.
  Compiler invocation checks are grouped into one counted action summary.
  Signature checks likewise use one function-count summary, with a separate
  count of functions whose signature validation is disabled.
- Explorer, feature graphs, and bundle loading accept `validate=False` to skip
  Spec semantic checks on already validated inputs. Project builds now validate
  Spec semantics once in the compiler; structural and artifact checks remain enabled.
- Engine validation checks now emit debug logs, including reasons for skipping
  inapplicable dataframe checks.
- Spec documents and execution plans now expose reusable resource indexes for
  profiles, features, actions or invocations, and arguments.
  Nested spec models also provide cached child, reference, and source views,
  reused by validation rules without additional declaration wrappers. Views
  use cached properties; construct a new model after editing indexed declarations.
- Function references now capture the implementation's docstring summary line
  as the function catalog `description`, with an explicit
  `ref.function(..., description=...)` override. The description is preserved
  in exported spec documents.
- Explorer function catalog presentation data includes argument, return,
  raise, and example documentation parsed from implementation docstrings when
  signature validation is enabled.
- Structural dataframe validation now follows each function kind's explicit
  dimension, row-count, fragment, and key-identity policies. Vectorized results
  independently preserve target row counts and key identities; dimensional
  changes do not imply either guarantee.

### Changed

- **Breaking:** Dimensions now declare keyed resolutions, and profiles select
  their row detail with an ordered `grain` of dimension-resolution references.
  Resolution parent links are local to their dimension, order keys must be
  selected by the grain, and descriptive `row_scope.grain` has been removed.
- **Breaking:** Replaced entity-owned datasets with globally keyed top-level
  `profiles` in spec version 4. Profile declarations now own their dimensions
  and may declare an optional `category`; removed the Entity model and authoring
  API. Execution plans are now version 4 and no longer carry `entity_id`.
  CLI summaries, previews, and Explorer labels now present profile terminology.
- **Breaking:** Project builds and feature-graph inspection replace `--verbose`
  with `--log-level {debug,info,warning,error,critical}` (default: `info`).
  Debug logging includes detailed build summaries and feature graph trees.
- Engine debug logs now group invocations and validation checks under headings
  with indentation and spacing, avoiding repeated dataframe descriptions.
- **Breaking:** `run` and `engine run` replace `--verbose` with
  `--log-level {debug,info,warning,error,critical}` (default: `info`).
  Debug logging includes execution details and validation traces without
  enabling dependency debug logs.
- **Breaking:** Removed the Jinja website renderer and its `Explorer.create_html`
  API. Project builds now publish a versioned Explorer JSON snapshot, served by
  the packaged static frontend or exported with `uptimely explorer export`.
- **Breaking:** Renamed `ExecutionResult.datasets` to `ExecutionResult.main_frames`.
  Values remain final dataframes keyed by dataset ID.
- Engine runtime assembly now uses a `MainFrame` per logical dataset and
  explicit `Fragment` contributions. Dimension-aware merge decisions and
  runtime validation are separate from generic dataframe backend operations;
  runtime state indexes `main_frames`, each owning its retained fragments.
  Function arguments and execution results remain ordinary dataframes.
- Runtime execution and validation now consume plan invocation metadata rather
  than Spec or Dataset objects. Invocations serialize ID columns, logical column
  types, and argument types; previously saved plans without this metadata must be
  rebuilt. Dataset resource-binding views have been removed. Physical `MainFrame`
  accumulators take ID column names instead of a Dataset.
- `Fragment.stage()` replaces `Fragment.from_invocation()`: it calls an invocation
  loader, validates the raw result when requested, and projects declared outputs,
  returning a fragment ready to merge without accepting a preloaded result.
- **Breaking:** Engine per-step validation is now opt-in with `uptimely run
  --validate` or `Engine.run(validate=True)`, for both eager and lazy frames.
  Normal runs skip runtime contract checks and join cardinality validation,
  avoiding repeated lazy-query execution. The `backend.validate_lazy_frames`
  configuration option has been removed.
- Function-kind attributes now drive dataframe and feature input-scope
  validation. Compilation also checks enabled implementation signatures for
  keyword-call compatibility and contradictions in supported argument and
  return annotations; missing annotations remain permitted.
- **Breaking:** Function kind identifiers are now typed as `FunctionKindId`,
  while `FunctionKind` is an immutable definition object with independent
  capability flags. `FUNCTION_KINDS` is now a read-only identifier-to-definition
  mapping; the parallel `FunctionReturns`, `FRAGMENT_KINDS`,
  `KIND_DATAFRAME_INPUT_COUNTS`, and `KIND_RETURN_KINDS` APIs have been removed.
  Serialized kind identifiers and their runtime behavior are unchanged.
- **Breaking:** Semantic validation rules now accept the spec document directly
  and raise on failure, replacing prepared-context and diagnostic-generator
  interfaces. Rules run according to explicit dependencies rather than legacy
  phase ordering, so documents with multiple faults may report a different
  first error. Public loading helpers still validate automatically.

### Fixed

- The GitHub Pages pump analytics demo now includes engine run information,
  debug logs, and ten-row profile previews. Static Explorer exports include the
  latest run and display results without requiring live API endpoints.
- Restored documentation builds by updating engine API module references and
  corrected broken links on the documentation homepage.

## [0.8.0] - 2026-10-28

### Added

- Added a public Python authoring API through `import uptimely as up`, including
  `Dataset`, `Action`, `Feature`, `Order`, `RowScope`, `Spec`, `@up.function`,
  and deferred references such as `up.ref.column()` and `up.ref.output()`.
- Added `conform`, `collapse`, and `expand` function kinds for dimensional
  operations, with explicit dimension-key selectors and matching-key validation.
- Added entrypoint package provenance to compiled plans, including installed
  distribution names and versions, and improved support for resolving functions
  from installed packages.
- Added a pump analytics external-workflow example and expanded documentation
  for dimensional modeling, execution architecture, and analytical function
  contracts.

### Changed

- **Breaking:** Python authoring now requires explicit `dimensions`, `entities`,
  and `datasets` registrations. Datasets declare `producers`, `publishers`, and
  `pipelines` as lists of `Action` objects with dataset-unique IDs, replacing
  `FunctionMapping` attributes and the `mappings` dictionary. Function
  definitions use `kind` instead of `operation`; migrate decorators and
  `ref.function(...)` calls to `@function(kind=...)` and `kind=...`.
- **Breaking:** Spec version 3 replaces each dataset's `mappings` object with
  `actions`. Version 1 and 2 Specs are rejected; migrate JSON Specs and rebuild
  generated bundles.
- **Breaking:** Function dataframe contracts now distinguish dimensional
  operations: `read` functions take no dataframe arguments, while `conform`,
  `collapse`, and `expand` take only their foreign/source dataframe and return
  target-dataset fragments. Dimensional functions must satisfy their declared
  dimension relationship and key selectors. Same-dataset fragments are
  validated and assembled by complete keys; the built-in runtime supports
  Polars `DataFrame` and `LazyFrame`.
- **Breaking:** Portable plans now use version 3 and represent planned steps as
  `invocations` with explicit function and action IDs and opaque invocation
  identifiers. Version 1 and 2 plans are rejected; rebuild bundles from their
  source Specs. Plan models and serialization are provided by
  `uptimely.execution_plan`.
- **Breaking:** Removed obsolete import aliases. Python authoring declarations
  are exposed from `uptimely` or `uptimely.spec.python`; document-model classes
  are imported from `uptimely.spec` or `uptimely.spec.model`. Row context,
  execution-plan models, project paths, CLI helpers, and function-kind
  vocabulary now live in their respective modules rather than the old forwarding
  modules and compiler exports.
- Explorer feature and invocation lineage now support dataset swimlanes in 2D,
  with cross-dataset dependency routing, dataset-based colors, stage columns,
  and selected-node dependency highlighting. Navigation is responsive on mobile,
  and graph details and controls are consistent across views.
- Execution plans no longer duplicate Spec-derived entities, functions, and
  datasets in `resources`; the build bundle's Spec is their source. Execution
  results expose invocation statuses.

### Fixed

- Spec validation now suggests a matching function kind for incompatible
  function signatures, warns instead of failing when declared features have no
  producer, and allows escape dependencies on features produced by any function
  kind.
- Engine execution validates foreign dataframe inputs and safely assembles
  same-dataset fragments while rejecting duplicate keys and feature collisions.


## [0.7.0] - 2026-10-23

### Added

- Added `uptimely build`, `uptimely run`, and `uptimely explore` shortcuts for
  project build, engine run, and Explorer serve. Project commands accept the
  project directory as an optional positional argument or through
  `--project-root`. `uptimely examples` downloads examples directly; the
  `examples download` form remains available.

### Changed

- **Breaking:** Python authoring now uses dataset classes with named declarative
  mappings and output-owned feature metadata. Replace dataset feature and
  mapping lists with named mapping attributes or dictionaries, and
  `Mapping(bind=...)` with `FunctionMapping(function=..., arguments=...,
  outputs=...)`. Declare operations with `@operation(...)` or
  `ref.function(..., operation=...)`, and output features with
  `Feature(name=...)`; mapping identifiers come from their declaration keys.
  The document model and exported JSON format are unchanged.
- **Breaking:** Execution results now index `datasets` by dataset ID and
  `calculated_outputs` by `(dataset_id, feature_id)`, without redundant entity
  IDs. Dataset IDs remain unique across the project.
- **Breaking:** Spec version 2 stores each entity's datasets as an object keyed
  by dataset ID instead of an array. Remove dataset `id` attributes and use the
  IDs as object keys. Version 1 and dataset arrays are rejected; update JSON
  sources and rebuild generated project artifacts.
- Execution plans no longer duplicate spec-derived entities, functions, and
  datasets in `resources`; the build bundle's spec is the source for those
  declarations.
- Explorer pages now share a project-name top bar, home link, build-scope badge,
  and consistent graph controls and details panels. Selecting graph nodes
  highlights their dependencies and dependents; reset clears the selection
  and fits the graph.

## [0.6.0] - 2026-10-22

### Added

- `uptimely engine run --preview [ROWS]` logs the first rows of each final
  dataset after successful execution. Omit the count to preview five rows;
  previews are opt-in and independent of `--verbose`.
- Python entrypoint modules expose `source_file` for their loaded file path or
  remote source URI.
- `uptimely.project.resolve_path` resolves explicit paths or defaults beneath
  the project root.

### Changed

- **Breaking:** Construct the engine with `Engine(bundle, config)` using a
  validated project build bundle and a required `EngineConfig`, then call
  `run()` instead of `execute()`. Direct plan input, resource overrides, and
  injected backend, resource-resolver, and callable-loader arguments are no
  longer supported. Resources and callable project context come from the bundle.
- **Breaking:** `EngineConfig` now validates the complete runtime configuration,
  with backend settings nested under `backend` and runtime bindings under `bind`.
  Use `EngineBackendConfig` for backend options instead of passing them directly
  to `EngineConfig`. Removed `ResourceResolver`, `CallableLoader`,
  `PlanResourceResolver`, and `EntrypointLoader` from the engine API.
- **Breaking:** Removed the redundant `print()` method from feature graphs.
  Use `print_graph()` for terminal output or `render_graph()` to return text.
- Project builds now log one success line by default; add `--verbose` for grouped
  build timing, source and resource counts, and plan details.
- Engine runs now report execution duration and dataset count, with feature
  scope and per-dataset feature counts under `--verbose`.
- CLI status and verbose output now use INFO-level Python logging.

### Fixed

- Explorer generation now reports entrypoint signature inspection errors
  instead of silently omitting return types when signature validation is enabled.

## [0.5.0] - 2026-10-21

### Changed

- **Breaking:** Spec documents now use integer `spec_version: 1` instead of
  `version: "0.2.0"`, and portable plans use integer `plan_version: 1` instead
  of `"0.2.0"`. Build manifests rename `schema_version` to `build_version`.
  Update existing specs and regenerate plans and build bundles.
- **Breaking:** Default spec discovery now checks `spec/spec.py` and
  `spec/spec.json` instead of `config/spec/spec.py` and
  `config/spec/spec.json`. Move specs to the new directory or select a source
  explicitly with `--python-spec` or `--json-spec`.


## [0.4.0] - 2026-10-20

### Added

- Per-function `validate_signature` option (default `true`) in JSON specs and
  Python references. Set it to `false` to skip implementation imports and
  signature checks during compilation and Explorer generation; spec contracts
  and runtime execution requirements remain unchanged.

### Changed

- **Breaking:** Project build CLI options `--entrypoint` and `--spec` are now
  `--python-spec` and `--json-spec`. The corresponding Python arguments to
  `build_project` and `load_spec_source` are now `python_spec` and `json_spec`.
- **Breaking:** Entrypoint helpers `load_callable`, `read_signature`,
  `FunctionSignature`, and `type_name` are replaced by the object-based
  `Entrypoint`, `Function`, `Signature`, and `TypeAnnotation` API. Use
  `Entrypoint(value).function.load()` or `.function.signature`.

## [0.3.0] - 2026-10-19

### Added

- The `escape` operation supports explicit external workflows. Escape mappings
  declare feature dependencies but bypass dataframe contracts; their arbitrary
  Python return values are not materialized as dataframe columns.
- Added `scripts/serve-docs.sh` to serve the project documentation.

### Changed

- **Breaking:** Removed `prepare_spec`, `PreparedSpec`, `Function`, and `Call`
  from the spec and top-level APIs, and removed `uptimely.spec.resolved`,
  `uptimely.spec.resolution`, and `validation.validate_prepared`. Use
  `validation.validate_spec(document)` for semantic validation and the compiler
  for executable invocations. Loading and Python conversion still validate
  automatically. Direct validation now follows loading's error precedence;
  duplicate calculated outputs are reported as conflicting mapping producers.
- Feature graphs expose declared function templates instead of resolved
  function objects. The spec document and portable plan formats are unchanged.

## [0.2.0] - 2026-10-19

### Added

- `uptimely project build` publishes a validated active bundle containing the
  spec, execution plan, and Explorer website. Python functions can be bound by
  callable or `path:function` entrypoint.

### Changed

- **Breaking:** `uptimely project build` replaces the standalone generation
  commands. Engine, Explorer, and MCP now consume the saved active build rather
  than compiling or regenerating artifacts; source changes require a rebuild.
- **Breaking:** Public APIs and CLI terminology are standardized on `spec` and
  `explorer`, with old names and artifact layouts removed. Spec authoring,
  parsing, and function-mapping interfaces have also changed.
- Portable plans now declare `plan_version` (`0.2.0`); regenerate plans in the
  previous format.
- Generated graph pages combine 2D and 3D views with an in-place selector that
  preserves the selected node.

### Fixed

- Missing generated inputs now produce actionable errors.

## [0.1.0] - 2026-10-14

### Added

- JSON analytics specifications, with Python authoring and JSON export.
- Feature dependency validation, graph analysis, and feature-level subgraphs.
- Compilation into portable, staged execution plans, including plans for
  selected features and their dependencies.
- A built-in Polars batch engine with runtime resource resolution.
- Generated analytics documentation with specification, dependency graph,
  execution plan, and data lineage views.
- An optional MCP server for specification introspection and feature execution.
- Runnable examples for authoring, compiling, documenting, and executing
  analytics.

## [0.0.1] - 2026-08-16

Placholder release to reserve the package name in PyPI.
- Spec loading and Python conversion accept `validate=False` to defer semantic
  checks while preserving structural parsing. Project builds validate source
  semantics in the compiler instead of repeating checks during source loading.
