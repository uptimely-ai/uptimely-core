# Release 4: Specification expressions, composition, and summaries

This is a planned release grouping, not a published software version.
These packages can ship independently of new execution capabilities.

## Work package: Braced reference migration

**Prerequisites:** Existing specification model, compiler, and runtime bindings.

| title | breaking | description |
|---|---|---|
| Migrate references to braced notation | Yes | Replace existing Spec reference and selector forms with `${...}` in fields that accept references, including feature, profile, dimension, operator, parameter, and path references. Keep bare identifiers in fields that do not use selector syntax. Preserve standalone reference types and existing compile-time and runtime resolution semantics. Version the Spec format, reject obsolete syntax with actionable migration guidance, and update Python authoring, plans, examples, documentation, and tests together. |

## Work package: String expressions and derived feature IDs

**Prerequisites:** Braced reference migration.

| title | breaking | description |
|---|---|---|
| Interpolate references in strings | Yes | Support multiple `${...}` references within binding strings and add `ref.string(...)` for Python authoring. Treat `$${` as a literal `${`, escape literal parts supplied to the helper, and never reinterpret substituted values as expressions. Preserve the type of standalone references, require embedded values to be strings, and reject malformed, unresolved, or incompatible references explicitly. Resolve structural references at compilation and params and paths at runtime without losing escapes or reevaluating inserted text. Version the format and explain how to escape previously literal expression-shaped strings. Cover nested bindings, multiple references, escaping, and mixed resolution phases in tests. |
| Derive feature IDs from references | Yes | Allow feature IDs to combine compile-time feature or profile identifiers and literal text, including feature declaration keys in JSON and `ref.string(...)` in Python. Resolve IDs before feature registration and interface validation, and report missing references, cycles, and duplicate resulting IDs. Do not allow runtime parameters or paths to determine feature IDs. Document migration of expression-shaped literal keys and update the cooling-pump example and focused tests. |

## Work package: Expression highlighting

**Prerequisites:** Braced reference migration and String expressions and derived feature IDs.

| title | breaking | description |
|---|---|---|
| Highlight specification expressions in the devcontainer | No | Provide a VS Code highlighting extension for Uptimely reference and interpolation syntax, including escaped expressions, and make it available in the devcontainer. Scope highlighting to Uptimely authoring files without changing unrelated JSON or Python files. Verify installation and representative highlighting, and document how to use it outside the devcontainer. |

## Work package: Specification summary

**Prerequisites:** Existing specification model.

| title | breaking | description |
|---|---|---|
| Print a concise spec summary | No | Add a public `Spec.print_summary()` method that prints a readable overview of a specification, and demonstrate it in the project README's Python example. |

## Work package: Specification composition

**Prerequisites:** Existing specification loading and semantic validation.
Keep merge rules independent of later execution capabilities.

| title | breaking | description |
|---|---|---|
| Merge JSON specification files | No | Read multiple JSON files and recursively merge objects before existing model and semantic validation. Accept identical overlaps; report conflicts with files and JSON paths. Arrays are whole values, not concatenated or deduplicated. Set the combined spec's name and source explicitly rather than merging contributor metadata. Fragments need not be semantically valid alone. Reuse reference, contract, producer and cycle checks. Do not add repository fetching, package discovery, version resolution, automatic namespacing or identifier rewriting. |
