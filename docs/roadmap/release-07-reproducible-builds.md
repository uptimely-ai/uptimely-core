# Release 7: Immutable build snapshots, dependency provenance, and source diagnostics

This is a planned release grouping, not a published software version. Work packages remain ordered by their stated prerequisites.

## Work package: Reproducible builds and diagnostics

Make builds identifiable and immutable, and source-loading failures actionable.

**Prerequisites:** No new execution capability; provenance records must evolve
with changes to specification and plan formats.

| title | breaking | description |
|---|---|---|
| Record execution requirements | No | Record callable module references, declared package requirements, and available package provenance in the build manifest. Aggregate distribution names and versions from the execution plan while keeping declared requirements distinct from observed entrypoint provenance. Record resolved source roots, selected Spec entrypoint, and project-source origin so module and package references can be interpreted. Provide checks for requirement availability and compatibility without executing analytical functions, for reuse by strict target-aware compilation and engine preflight. Distinguish declared requirements from best-effort import analysis. Dynamic and transitive imports cannot be exhaustively inferred. Do not install dependencies automatically. |
| Preserve immutable build snapshots | No | Published artifacts retain fixed specification, mapping bindings, plan, and callable implementation source with stable build identity. Package callable code in the bundle as a wheel for packaged projects or a deterministic source archive for supported pure-Python projects. Record archive content hashes, project-relative source roots, the selected Spec entrypoint, and module-to-file mappings. Load implementations from the artifact at runtime rather than mutable project files. Version the build manifest when its artifact schema changes and report when an older build needs rebuilding. An import path or source fingerprint alone does not freeze implementation. Record dependency requirements and provenance separately. Bundling project source does not bundle third-party dependencies. Mark source outside the project bundle as external rather than implying the build is self-contained. Changed logic or bindings require a new build, not a new authoring identity for every function or mapping. Runtime overrides must not mutate published artifacts. |
| Improve build-source diagnostics | No | Distinguish malformed `module:attribute` entrypoints, missing spec sources and import failures inside otherwise valid modules. Preserve the underlying exception cause and actionable message, and offer a verbose traceback option. Cover Python and JSON source selection, project-directory discovery and nested import failures in tests; document the current CLI syntax rather than introducing a duplicate project-directory option. |
