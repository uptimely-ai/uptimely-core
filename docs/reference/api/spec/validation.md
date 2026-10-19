# Spec validation

`uptimely.spec.validation` exports semantic validation functions and the
structured `SpecError` exception. For normal loading and authoring, use
[load_spec or from_python](api.md), which perform the
required validation for you.

The sections below document the exported interfaces in their defining modules,
not the internal rule helpers. Call `validate_spec(document)` after editing a
document directly. Each invocation builds fresh lookup indexes, reads the
document's mappings, and leaves the document unchanged. Validation does not
import executable function implementations.

## Responsibilities and phase order

Document validation checks declared relationships and dataflow, not generated
callables. Its ordered phases are:

1. Vectorize output declarations, dataset IDs, feature ownership, and local
   calculation/write dependencies.
2. Dimension parents, entity dimensions, and dataset ordering.
3. Mapping outputs and producer uniqueness/completeness.
4. Collapse source scope, mapping inputs, row context, and mapping cycles.
5. Binding arguments, function contracts, and mapping contracts.

The preliminary checks preserve loading's established error precedence.
Direct validation now uses the same sequence as loading and Python conversion.
Duplicate vectorize outputs are reported by mapping producer validation rather
than by validating a second collection of generated calls.

The coordinator in `validation.spec` passes per-invocation indexes to domain
validators. Add declaration rules to the appropriate domain phase, keeping
declaration order and testing the first error when faults overlap. The compiler
separately checks executable signatures, invocation dependencies, and plan
schedulability.

## Internal organization

The public interface remains `validate_spec(document) -> None`. Internal
modules separate orchestration from domain checks:

| Module in `uptimely.spec.validation` | Responsibility |
| --- | --- |
| `spec` | Explicit phase order and intermediate artifacts |
| `context` | Non-validating indexes, mapping locations, and resolved-source data |
| `dataset` | Dataset IDs and ordering dimensions |
| `dimensions` | Dimension declarations and parent relationships |
| `functions` | Binding arguments, nested selector types, and function contracts |
| `mapping_outputs` | Early calculation outputs, ownership, and producer accounting |
| `mapping_inputs` | Input references, collapse source scope, and row context |
| `mapping_contracts` | Dataframe input resolution and operation-specific contracts |
| `dependencies` | Local calculation/write scope and mapping-cycle checks |
| `errors` | Structured validation errors |

Indexes retain all duplicate candidates until the responsible phase rejects
them. `MappingLocation` carries the declaring entity, dataset, and mapping key
alongside the mapping model. Shared traversal in `uptimely.spec.references`
preserves declaration order without resolving functions or sources. Binding
errors retain dictionary-key paths; contract errors retain model-ID paths.

Output validation produces the feature-to-producer index. Collapse validation
uses indexed feature owners to infer each source, validates that mapping before
advancing to the next one, and returns its successful source resolution.
Input and contract phases reuse those sources instead of inferring them again.
Input validation returns the mapping dependency graph, which the coordinator
passes to cycle validation. These artifacts are explicit local values, not
global caches or additional fields attached to the document.

Operation contracts resolve common dataframe arguments before selecting a
handler. Vectorize and write share a local-dataset contract; conform and expand
share join-input checks before their distinct dimensionality rules.

### Adding or changing a rule

1. Choose the domain module and existing phase that owns the invariant. A new
   class or phase is not needed for every rule.
2. Use `validate_<subject>` for collection phases and `_validate_<subject>` for
   private cohesive checks. Validation raises on invalid input; it may return
   an explicitly documented artifact, but not a success boolean.
3. Use `iter_<subjects>` for traversal and `resolve_<subject>` for fallible
   resolution. Keep index construction non-validating so an eager lookup cannot
   change the first reported error.
4. Keep a condition and its error close together. Loops and comprehensions are
   allowed in validation functions; avoid one-line wrappers that accept a
   precomputed boolean merely to raise an exception.
5. Preserve mapping-first order within a phase. Checking one rule across all
   mappings before applying the next rule changes which error is reported.
6. Add focused tests for valid inputs and overlapping faults. Preserve exception
   classes, messages, structured codes, paths, and the public exports. For
   changes to reference resolution, test both indexed validation and existing
   callers that resolve directly from the document.

Semantic validation must remain independent of executable entrypoints and
compiler-generated callables. Do not reintroduce prepared-spec objects or move
signature and schedulability checks out of the compiler.

<div class="api-reference" markdown="1">

## errors

`uptimely.spec.validation.errors` defines validation errors with a code
and document path.

::: uptimely.spec.validation.errors
    options:
      heading_level: 3
      show_root_heading: false
      members: [SpecError]

## spec

`uptimely.spec.validation.spec` orchestrates document validation.

::: uptimely.spec.validation.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_spec]

## dataset

::: uptimely.spec.validation.dataset
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_dataset_ids]

</div>
