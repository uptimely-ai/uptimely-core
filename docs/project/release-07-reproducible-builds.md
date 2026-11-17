# Release 7: Immutable build snapshots, dependency provenance, and source diagnostics

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Execution requirements and provenance

Record declared requirements and observed source provenance without executing
analytical functions.

**Prerequisites:** Existing specification and plan formats.

| title | breaking | description |
|---|---|---|
| Record declared package requirements | No | Store declared package requirements separately from best-effort import analysis. Do not claim dynamic or transitive imports can be exhaustively inferred. |
| Record callable and source provenance | No | Record callable module references, resolved source roots, selected Spec entrypoint, and project-source origin in the build manifest. Keep declared requirements distinct from observed entrypoint provenance. |
| Check requirement availability | No | Aggregate distribution names and versions from the execution plan and check availability and compatibility without running analytical functions. Do not install dependencies automatically. Reuse the checks in strict target-aware compilation and engine preflight. |

## Work package: Immutable build snapshots

Ensure a published build runs the implementation and bindings captured when it
was created.

**Prerequisites:** Execution requirements and provenance.

| title | breaking | description |
|---|---|---|
| Package callable source in builds | No | Include callable code as a wheel for packaged projects or a deterministic source archive for supported pure-Python projects. Mark source outside the project bundle as external. Bundling project source does not bundle third-party dependencies. |
| Record source archive identity | No | Store archive hashes, project-relative source roots, selected Spec entrypoint, and module-to-file mappings. An import path or source fingerprint alone does not freeze implementation. |
| Load implementations from the build | No | Load callables from the published artifact rather than mutable project files. Changed logic or bindings require a new build. |
| Version and protect build manifests | No | Version the manifest when its artifact schema changes and report when an older build needs rebuilding. Runtime overrides must not mutate published artifacts. |

## Work package: Build-source diagnostics

Make source-selection and import failures actionable.

**Prerequisites:** Existing Python and JSON source loading.

| title | breaking | description |
|---|---|---|
| Distinguish source and entrypoint failures | No | Report malformed `module:attribute` entrypoints, missing Spec sources, and import failures inside valid modules as distinct errors. |
| Preserve import causes and tracebacks | No | Retain the underlying exception cause and actionable message, with an option to show a verbose traceback. |
| Test and document source diagnostics | No | Cover Python and JSON source selection, project-directory discovery, and nested import failures. Document the existing CLI syntax without adding a duplicate project-directory option. |
