# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased]

### Added

- CLI commands for compiling execution plans (`uptimely plan build`), inspecting
  feature dependencies (`uptimely spec feature_graph`), and running workflows
  (`uptimely engine run`). Engine execution compiles by default; use
  `--compile false` to run a saved plan.

### Changed

- `uptimely docs serve` now builds the website from the project's specification before serving it.

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
