# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
While the version is `0.x`, minor releases may include breaking changes.

## [Unreleased] - 2026-10-07

Initial public release.

### Added

- Python API reference generated from source, with documentation validation on
  pull requests and automatic GitHub Pages publishing from `main`.
- Declarative specification model with JSON export.
- Optional dataset logical ordering by dimension, with explicit ascending or
  descending directions, JSON and Python authoring, and reference validation.
- Mapping-level row-context requirements with fixed dimension-based time and
  integer-step windows, row counts, unbounded directions, Python window
  consolidation, and portable plan metadata.
- Compiler producing portable, staged execution plans.
- Built-in batch engine with a Polars dataframe backend.
- Documentation and feature-graph generation from specifications.
- MCP server exposing specification introspection and feature execution tools.
- Runnable examples under `examples/` with an automated test suite.
- `uptimely examples download` command to fetch examples from the public GitHub
  repository, with revision and destination options.

### Changed

- Moved the generated feature graph to `spec/graph.html` beneath Specification.
  Rebuilds remove the former `graph/feature_graph.html` page.

- Unified the generated website's navigation, heading, and dashboard icons with
  a shared section palette and distinct specification-resource accents.

- Redesigned the generated website homepage as a project dashboard with resource
  and plan counts and a Specification, Feature lineage, and Execution plan journey.
  The site brand now returns to the dashboard, including custom index filenames.
- **Breaking:** HTML generation now always produces the complete documentation
  website through `Documentation.create_html`, `uptimely.docs.docs.create_html`,
  or `uptimely docs build`. Renamed the CLI command from `generate` to `build`.
  Removed `Specification.create_html`,
  `FeatureGraph.export_html` (including subsets), and `ExecutionPlan.export_html`.
  Specification and plan JSON exports and graph analysis remain available.
- Standardized implementation and test imports on module-qualified references,
  preserving package-level public API re-exports and leaving examples unchanged.
- Moved function-local imports to module scope while keeping S3 dependencies
  optional and reporting the required extra when unavailable.
- Mappings declare explicit `features.inputs` and `features.outputs`; Python
  declarations use `inputs=` and `outputs=`. Identifier arguments do not imply
  materialized data dependencies.
- All data-producing functions, including vectorize and collapse, return
  dimension-keyed dataframes. Functions perform grouping, output naming, and
  literal construction; the engine validates and joins returned fragments.
  Standalone expressions, series, scalar returns, and expression dictionaries
  are no longer supported. Re-export specifications and recompile plans.
- Row context now belongs to the mapping, with optional `dimension` and fixed
  `before`/`after` requirements. Removed explicit `extent` and function
  `partitioning`. Dataset order is inherited; grouping stays in functions.
- Added explicit `.id` and `.dataframe` argument selectors.
- Removed legacy portable-plan serialization fields and API aliases, engine
  runtime-state accessors, and pre-row-scope specification input normalization.
  Portable plans now serialize and load only their canonical schema; execution
  results expose runtime outputs.

### Fixed

- Aligned generated website routes and relative navigation on `spec/`, `graph/`,
  and `plan/` subdirectories, including custom index names and plan source links.
- Corrected stale symbol references in specification models, compilation,
  feature graphs, the engine, and tests that prevented pytest collection and
  blocked the pre-push hook.

## [0.0.1] - 2026-08-16

Placholder release to reserve the package name in PyPI.
- Combined each generated graph section into one page with an in-place 2D/3D
  selector, defaulting to 2D and preserving selected node details. Sidebar links
  now use `graph/feature_graph.html` and `plan/graph.html`; rebuilds remove
  obsolete dimension-specific graph pages.
