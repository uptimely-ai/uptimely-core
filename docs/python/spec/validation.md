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
invocations. Its ordered phases are:

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

The coordinator in `validation.spec` delegates to five named phase generators,
making the validation sequence visible at the top level while retaining lazy
first-error behavior. Each phase passes the same fresh `SpecValidationContext`
facts to the explicit domain rules. Add
declaration rules to the appropriate domain phase, keeping
declaration order and testing the first error when faults overlap. The compiler
separately checks executable signatures, invocation dependencies, and plan
schedulability.

## Internal organization

The public interface remains `validate_spec(document) -> None`. Internal
modules separate orchestration from domain checks:

| Module in `uptimely.spec.validation` | Responsibility |
| --- | --- |
| `spec` | Named lazy generators for the ordered validation phases |
| `context` | All traversal, indexing, reference extraction, and prepared declaration facts |
| `dataset` | Dataset IDs and ordering dimensions |
| `dimensions` | Dimension declarations and parent relationships |
| `functions` | Binding arguments, nested selector types, and function contracts |
| `mapping_outputs` | Early calculation outputs, ownership, and producer invariants |
| `mapping_inputs` | Input references, collapse source scope, and row context |
| `mapping_contracts` | Dataframe reference validity and operation-specific contracts |
| `dependencies` | Local calculation/write scope and mapping-cycle checks |
| `errors` | Structured validation errors |

The context retains duplicate candidates, missing references, and ancestry
cycles as facts rather than raising semantic errors during preparation.
Domain validators decide whether those facts are acceptable. Indexes and graph
traversal results are prepared lazily where appropriate and cached only on the
current context. Revalidating an edited document builds a new context.

`DatasetLocation` represents dataset declarations, feature owners, and inferred
collapse sources; separate `FeatureOwner` and `CollapseSource` wrappers are not
needed. Feature occurrence order is retained independently of dataset order.
`MappingLocation` composes a `DatasetLocation`, retaining both dictionary-key
binding paths and model-ID contract paths without copying its entity and dataset.
`MappingFacts` derives entity dimensions and local features from that shared
location instead of storing repeated copies for every mapping. Other frozen
dataclasses are retained for facts shared by multiple atomic checks, such as
collapse-source and dataframe relationships. Binding names, selector types, and
function contracts are read from their declarations as the coordinator reaches
those phases, rather than being copied into one-use wrapper records. Use
dataclasses for shared internal records, not a separate class for every
invariant. Specification models remain Pydantic models.

The context prepares producer occurrences and coverage, collapse source
candidates, row-context requirements, flattened binding selectors, dataframe
inputs, and the mapping dependency graph. Source inference is shared by the
collapse, row-context, and mapping-contract phases. No validator constructs
indexes or returns intermediate artifacts to the coordinator. One-pass phases
consume dependency and row-context facts through iterators instead of building
temporary tuples that validation would immediately traverse once.

Each phase checks one declaration's invariants before advancing to the next.
Output coverage follows all mappings in its dataset; dataframe arguments
precede operation-specific relationships. Vectorize and write share local
dataset checks; conform and expand share join-input checks.

Escape mappings require explicit, nonempty feature input and output lists.
Their references participate in normal ownership, producer, unknown-reference,
and cycle checks, and may connect features across datasets. Binding arguments
are still validated, including any explicitly bound dataframe references, but
escape does not receive the dataframe relationship checks used by controlled
operations. Its declared features need not match Python parameters or return
values. Compilation retains their dependencies; execution invokes the function
and ignores its return value without materializing declared outputs.

### Adding or changing a rule

1. Choose the domain module and existing phase that owns the invariant. A new
   class or phase is not needed for every rule.
2. Define entry points as `_validate_<subject>(context: SpecValidationContext)
   -> None` and mark them with `@context_module.spec_validation`. The identity
   decorator statically checks the callable interface without wrapping it,
   injecting context, or registering rules globally. Add entry points explicitly
   to the typed list in `validate_spec`.
3. Put traversal, normalization, index construction, source candidate discovery,
   and graph walks on `SpecValidationContext`. Preparation must retain invalid
   declarations without raising validation errors or hiding duplicate candidates.
4. Keep conditions and their errors together in domain modules. Comprehensions,
   `next()`, `all()`, and `any()` may inspect prepared facts; explicit `for` and
   `while` loops belong to the context, except for the coordinator's rule loop.
   Cohesive `_..._error` helpers may describe the first violation as an exception
   or `None`; the entry point raises the first described error immediately.
   They do not cache exceptions, return success booleans, or change exceptions.
5. Preserve mapping-first order within a phase. Checking one rule across all
   mappings before applying the next rule changes which error is reported.
6. Add focused tests for valid inputs and overlapping faults. Preserve exception
   classes, messages, structured codes, paths, and the public exports. For
   changes to reference resolution, test both indexed validation and existing
   callers that resolve directly from the document.

Semantic validation must remain independent of executable entrypoints and
compiler-generated invocations. Do not reintroduce prepared-spec objects or move
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
