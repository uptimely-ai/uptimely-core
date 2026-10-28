# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased]

### Added

- Author workflows with `import uptimely as up`: `up.Dataset`, `up.Action`,
  `up.Feature`, `up.Spec`, and `@up.function`. `up.PythonSpec` remains an alias
  for `up.Spec`. Use `up.ref.dataframe()`
  (optionally with a dataset ID), `up.ref.column(name)`, and
  `up.ref.output(name)` for deferred argument wiring. Output references validate
  membership in the containing action's declared outputs without adding input
  dependencies. Existing reference helpers remain supported.

### Changed

- **Breaking:** Root-level `uptimely.Spec`, `uptimely.Dimension`, and
  `uptimely.Entity` now expose Python authoring declarations.
  Import document-model classes from `uptimely.spec` or `uptimely.spec.model`.

- **Breaking:** Python datasets now declare `producers`, `publishers`, and
  `pipelines` lists of `Action` objects instead of named `FunctionMapping`
  attributes or a `mappings` dictionary. Actions require an explicit dataset-unique
  `id`; collections validate function kinds and follow normal Python replacement
  inheritance. Import `Action` from `uptimely.spec.python` or its `actions` module.
  Spec version 3 uses an `actions` object in each dataset instead of `mappings`;
  rename that key and set `spec_version` to `3` when migrating version 2 documents.

- **Breaking:** Function definitions now use `kind` instead of `operation`.
  Python authoring uses the optional `@function(kind=...)` decorator from
  `uptimely.spec.python` (defined in its `functions` module), replacing `@kind(...)`.
  Undecorated implementations use `ref.function(..., kind=...)`. Callable
  references inherit decorated kinds and reject conflicting explicit kinds.

- **Breaking:** `PythonSpec` requires explicit `dimensions`, `entities`, and
  `datasets` sequences instead of inferring registrations. Dataset entities may
  reference registered entities by ID or object, and entity dimensions may mix
  registered dimension IDs and objects. Undeclared references and duplicate
  registrations are rejected.

- **Breaking:** `read` functions take no dataframe arguments; `conform`,
  `collapse`, and `expand` take only their foreign/source dataframe and return
  target-dataset fragments. Dimensional operations declare matching dimension
  keys explicitly. Same-dataset fragments are validated and assembled by
  complete keys with a full outer join, preserving partial coverage and
  rejecting duplicate keys and feature collisions. The built-in runtime
  supports Polars `DataFrame` and `LazyFrame` only.

- Spec validation now suggests a matching function kind when a function's
  declared return kind or dataframe argument count conflicts with its kind. It
  never changes the function kind automatically.
- Spec validation warns about declared features with no producing mapping
  instead of rejecting the Spec, and allows escape dependencies on features
  produced by any function kind.
- Documented the purity contract for analytical calculations and added an
  example test that verifies a calculation leaves its input unchanged.
- **Breaking:** Execution plans now use `invocations` with explicit `function_id`
  and `mapping_id` fields, opaque invocation IDs, and version 3. Invocation
  function categories are named `function_kind`. Execution results expose
  `invocation_statuses`. Version 1 and 2 plans are rejected; rebuild generated
  bundles from their source Specs.
- **Breaking:** Removed the unused `CallableNode.to_render_data()`,
  `CallableGraph._node_data()`, `CallableGraph._node_key()`,
  `CallableGraph.print_graph()`, and `CallableGraph.print()` presentation
  helpers. For textual output from an existing callable graph, use
  `graphable.views.texttree.create_topology_tree_txt(graph.graph)`.

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
