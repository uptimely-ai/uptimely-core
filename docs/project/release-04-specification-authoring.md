# Release 4: Specification expressions, composition, and summaries

This is a planned release grouping, not a published software version.
These packages can ship independently of new execution capabilities.

## Work package: Braced reference migration

**Prerequisites:** Existing specification model, compiler, and runtime bindings.

| title | breaking | description |
|---|---|---|
| Migrate reference fields to braced notation | Yes | Replace existing reference and selector forms with `${...}` for feature, profile, dimension, operator, parameter, and path references. |
| Preserve literal identifiers and reference types | Yes | Keep bare identifiers in fields without selector syntax and preserve standalone reference types and existing resolution semantics. |
| Version the reference syntax | Yes | Version the Spec format and reject obsolete syntax with actionable migration guidance. |
| Update reference authoring and examples | Yes | Update Python authoring, plans, examples, documentation, and tests for the braced notation. |

## Work package: String expressions and derived feature IDs

**Prerequisites:** Braced reference migration.

| title | breaking | description |
|---|---|---|
| Parse braced references in strings | Yes | Support multiple `${...}` references in binding strings. Treat `$${` as a literal `${` and reject malformed or unresolved references. |
| Add the Python string-reference helper | Yes | Add `ref.string(...)` and escape literal parts supplied to it. Never reinterpret substituted values as expressions. |
| Resolve string references by phase | Yes | Preserve standalone reference types and require embedded values to be strings. Resolve structural references at compile time and parameters and paths at runtime without losing escapes or reevaluating inserted text. |
| Validate string expressions and migration | Yes | Reject incompatible references, version the syntax, and explain how to escape formerly literal expression-shaped strings. Test nesting, multiple references, escaping, and mixed resolution phases. |
| Derive feature IDs from references | Yes | Allow JSON feature keys and Python declarations to combine compile-time feature or profile IDs with literal text. Resolve IDs before registration and interface validation. |
| Validate derived feature IDs | Yes | Report missing references, cycles, and duplicate results. Disallow runtime parameters and paths in feature IDs. Update migration guidance, the cooling-pump example, and focused tests. |

## Work package: Expression highlighting

**Prerequisites:** Braced reference migration and String expressions and derived feature IDs.

| title | breaking | description |
|---|---|---|
| Add Uptimely expression highlighting | No | Provide a VS Code extension for reference, interpolation, and escaped-expression syntax in Uptimely authoring files. |
| Package highlighting in the devcontainer | No | Make the extension available in the devcontainer without changing unrelated JSON or Python files. |
| Verify and document expression highlighting | No | Test installation and representative highlighting, and explain use outside the devcontainer. |

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
| Recursively merge JSON objects | No | Read multiple JSON files and recursively merge their objects before model and semantic validation. |
| Diagnose conflicting specification values | No | Accept identical overlaps and report conflicting values with file names and JSON paths. |
| Preserve array and source metadata semantics | No | Treat arrays as whole values. Set the combined Spec name and source explicitly instead of merging contributor metadata. |
| Validate the merged specification | No | Allow fragments that are not valid alone, then reuse existing reference, contract, producer, and cycle checks on the combined Spec. |
| Keep composition scope bounded | No | Do not add repository fetching, package discovery, version resolution, automatic namespacing, or identifier rewriting. |
