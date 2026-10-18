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

- `uptimely project build` builds analytics JSON and compiles a saved execution
  plan in one command without executing the workflow. It supports standard
  source discovery, explicit entrypoints, and JSON sources.
- `uptimely analytics build` discovers standard Python or JSON sources under
  `config/analytics/`. Use `--entrypoint` or `--analytics` to select a source explicitly;
  ambiguous standard sources require an explicit selection.
- `uptimely analytics build` exports a module's `PythonAnalytics` to JSON,
  replacing the removed example export runners in documentation CI and MCP setup.
- CLI commands for compiling execution plans (`uptimely plan build`), inspecting
  feature dependencies (`uptimely analytics feature-graph`), and running workflows
  (`uptimely engine run`). Engine execution compiles by default; use
  `--compile false` to run a saved plan.

### Changed

- Explorer CLI commands now render a saved execution plan instead of recompiling
  analytics. The plan defaults to `_generated/compile/execution_plan.json`; use
  `--plan` to select another file and `uptimely project build` to prepare inputs.
  The Python API accepts `plan=` and still compiles when it is omitted.
- Analytics build now uses `--entrypoint module:attribute` instead of `--module`.
  The selected attribute must be a `PythonAnalytics` instance. Conventional
  discovery still selects `python_analytics` from the standard Python source.
- Renamed `uptimely analytics export` to `uptimely analytics build`. The options
  and JSON output are unchanged; the old command is no longer accepted.
- Python API documentation now follows the source package layout, with separate
  package pages, module navigation, and visually separated class and function
  entries. Coverage includes entrypoint loading, storage, function contracts,
  validation, JSON helpers, and exported graph types.
- Analytics now separates document models, Python authoring, JSON I/O, and
  prepared analysis. Removed the old JSON model/helper modules and
  `AnalyticsParser`/`AnalyticsSerializer`; use `load_analytics`, `from_python`,
  `prepare_analytics`, and `write_document` instead of model I/O methods.
  Python declarations use `to_model()` and `to_dict()`, with one shared
  JSON document format. Derived calls/functions are stored in `PreparedAnalytics`,
  not `Analytics`. Automatic function catalogs reject all conflicting metadata,
  and entity declarations must be passed through `entities=`, not `datasets=`.
- Feature graph HTML rendering and `GraphStyle` now belong to
  `uptimely.explorer.graph_render`; imports from
  `uptimely.analytics.feature_graph.render`,
  `uptimely.analytics.feature_graph.GraphStyle`, and
  `uptimely.analytics.GraphStyle` have been removed.
- Python analytics declarations now use `mapping.Mapping` with operation metadata
  on `ref.function`; operation-specific mapping classes have been removed.
- Portable plans now declare `plan_version` (`0.2.0`) and omit
  `analytics_version`. The built-in loader rejects unsupported plan versions;
  regenerate saved plans to use the current format.
- Python function bindings now require `ref.function(callable_or_entrypoint)`,
  accepting a Python callable or a `path:function` string. Local Python files,
  HTTPS source URLs, and S3 source URIs support signature inspection and execution.
- `uptimely explorer serve` now builds the website from the project's Analytics before serving it.
- Renamed the analytics documentation CLI command from `docs` to `explorer`.
- Example project analytics and engine settings now live under `config/`;
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
