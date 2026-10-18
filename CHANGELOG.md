# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased]

### Fixed

- Devcontainers mount the checkout's parent directory at its host path so
  sibling Git worktrees remain visible to Git and VS Code.

### Added

- `uptimely project build` validates the complete spec, compiles one plan, and
  publishes a manifest, spec, plan, and Explorer website as one active bundle.
  It supports standard source discovery, explicit entrypoints, JSON sources,
  and scoped feature selection without executing workflow functions.
- CLI commands for inspecting feature dependencies (`uptimely spec feature-graph`)
  and running the active saved execution plan (`uptimely engine run`).

### Changed

- The optional MCP server now reads and executes the validated saved build. It
  no longer exposes plan compilation or feature-specific recompilation; use
  `uptimely project build` to select a plan scope and `reload_build` to refresh it.
- Renamed the project domain, public APIs, CLI commands and options, project
  paths, examples, and documentation to use `spec`. Previous names and inputs
  are removed; no compatibility aliases or legacy handling remain.
- Explorer CLI commands now render a saved execution plan instead of recompiling
  spec. The plan defaults to `_generated/compile/execution_plan.json`; use
  `--plan` to select another file. The Python Explorer API accepts `plan=` and
  compiles when it is omitted.
- `uptimely engine run` now validates and executes the plan from
  `_generated/build/`. It no longer compiles from source or accepts spec,
  feature-selection, or arbitrary plan-path overrides.
- CLI artifact generation is provided by `uptimely project build`; the
  standalone spec and plan build commands have been removed.
- Python API documentation now follows the source package layout, with separate
  package pages, module navigation, and visually separated class and function
  entries. Coverage includes entrypoint loading, storage, function contracts,
  validation, JSON helpers, and exported graph types.
- Spec now separates document models, Python authoring, JSON I/O, and
  prepared analysis. Removed the old JSON model/helper modules and
  `SpecParser`/`SpecSerializer`; use `load_spec`, `from_python`,
  `prepare_spec`, and `write_document` instead of model I/O methods.
  Python declarations use `to_model()` and `to_dict()`, with one shared
  JSON document format. Derived calls/functions are stored in `PreparedSpec`,
  not `Spec`. Automatic function catalogs reject all conflicting metadata,
  and entity declarations must be passed through `entities=`, not `datasets=`.
- Feature graph HTML rendering and `GraphStyle` now belong to
  `uptimely.explorer.graph_render`; imports from
  `uptimely.spec.feature_graph.render`,
  `uptimely.spec.feature_graph.GraphStyle`, and
  `uptimely.spec.GraphStyle` have been removed.
- Python spec declarations now use `mapping.Mapping` with operation metadata
  on `ref.function`; operation-specific mapping classes have been removed.
- Portable plans now declare `plan_version` (`0.2.0`) and omit
  `spec_version`. The built-in loader rejects unsupported plan versions;
  regenerate saved plans to use the current format.
- Python function bindings now require `ref.function(callable_or_entrypoint)`,
  accepting a Python callable or a `path:function` string. Local Python files,
  HTTPS source URLs, and S3 source URIs support signature inspection and execution.
- `uptimely explorer serve` now builds the website from the project's Spec before serving it.
- Renamed the spec documentation CLI command from `docs` to `explorer`.
- Example project spec and engine settings now live under `config/`;
  `uptimely engine run` defaults to `config/engine.json` beneath the project root.

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
- Combined each generated graph section into one page with an in-place 2D/3D
  selector, defaulting to 2D and preserving selected node details. Sidebar links
  now use `graph/feature_graph.html` and `plan/graph.html`; rebuilds remove
  obsolete dimension-specific graph pages.
