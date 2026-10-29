# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased]

### Changed

- **Breaking:** Semantic validation rules now accept the spec document directly
  and raise on failure, replacing prepared-context and diagnostic-generator
  interfaces. Rules run according to explicit dependencies rather than legacy
  phase ordering, so documents with multiple faults may report a different
  first error. Public loading helpers still validate automatically.

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
