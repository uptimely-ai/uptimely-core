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
- Feature-level row-context requirements with time, integer-step, and row
  extents, unbounded context, Python argument annotations, and portable plan
  metadata. Replaces the function-template `input_scope` field.
- Compiler producing portable, staged execution plans.
- Built-in batch engine with a Polars dataframe backend.
- Documentation and feature-graph generation from specifications.
- MCP server exposing specification introspection and feature execution tools.
- Runnable examples under `examples/` with an automated test suite.
- `uptimely examples download` command to fetch examples from the public GitHub
  repository, with revision and destination options.

### Changed

- Collapse mappings now use a normal function `binding`, without `source` or
  `group_by`. The compiler infers the input dataset from bound features;
  inputs spanning datasets require an explicit expand first.
  The engine infers grouping from the target entity dimensions and wraps
  the function expressions in backend grouping. Reducers are cataloged
  under `functions.collapse`. Removed dataframe collapse wrapper functions,
  `functions.aggregate`, and the Python `Aggregation` / `aggregation` API.
  Old specifications and collapse plans are not supported.
- Removed legacy portable-plan serialization fields and API aliases, engine
  runtime-state accessors, and pre-row-scope specification input normalization.
  Portable plans now serialize and load only their canonical schema; execution
  results expose runtime outputs.

## [0.0.1] - 2026-08-16

Placholder release to reserve the package name in PyPI.
