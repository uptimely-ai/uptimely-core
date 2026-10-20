# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased]

### Added

- Function definitions and Python references accept and serialize
  `validate_signature`, defaulting to `true`. Setting it to `false` skips compiler
  signature inspection and Python return-annotation checks without removing the
  function from the plan. Documentation support will follow separately.

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
