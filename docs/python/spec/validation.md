# Spec validation

`uptimely.spec.validation` exports semantic validation functions and the
structured `SpecError` exception. For normal loading and authoring, use
[load_spec or from_python](api.md), which perform the
required validation for you. Pydantic model validation checks the document
shape and field types. `validate_spec(document)` checks semantic relationships
between those declarations.

The sections below document the exported interfaces in their defining modules,
not the internal rule helpers. Call `validate_spec(document)` after editing a
document directly. Each invocation builds fresh lookup indexes, reads the
document's actions, and leaves the document unchanged. Validation does not
import executable function implementations.

For the validation responsibilities of the document model, Spec, compiler, and
engine, see [Spec validation](../../components/spec.md#validation).

## Reporting and prerequisite contract

`validate_spec(document)` remains the public raising entry point and returns
`None` for a valid document. Semantic validation is fail-fast: it raises the
first actionable semantic error as a `SpecError`, which remains a `ValueError`.
It does not aggregate or expose later errors. Pydantic continues to report
document-shape and field-constraint errors separately.

Every semantic error has a stable, lower-case `code` and a `path`. Codes
identify the violated rule rather than being derived from the human-readable
message. A path is a tuple of mapping keys and sequence indexes locating the
offending declaration or field in the document; the empty tuple identifies
the document root. The exception message is for people, while `code` and
`path` are the machine-readable diagnostic contract.

Rule execution follows explicit data prerequisites, not historical
first-error precedence:

1. Validate declarations and establish unambiguous declaration indexes.
2. Resolve references against those declarations, including collapse-source
   candidates.
3. Run semantic checks that consume resolved declarations.
4. Validate dependency graphs after their nodes and edges are known.

A check runs only when its required facts are available. An invalid or
ambiguous prerequisite blocks checks that consume that fact; it must not be
replaced with an empty collection, a guessed owner, or an unresolved value.
Checks that do not depend on that fact are not thereby considered invalid.
Because reporting is fail-fast, however, validation stops at the first
diagnostic and does not promise to report other independent errors.

Within a prerequisite stage, validation order is deterministic and follows
document declaration order and the defined topic-rule sequence. This provides
repeatable first errors without making legacy phase precedence part of the
contract. Changes to which error is first are intentional when required by
these prerequisites; codes and paths identify the reported rule and location.

The implementation applies the rules in a fixed topic sequence and stops at
the first returned diagnostic. The compiler separately checks implementation
signatures, selected-plan feasibility, and invocation dependency ordering.

## Current implementation organization

The public interface remains `validate_spec(document) -> None`. Internal
modules separate orchestration from domain checks:

| Module in `uptimely.spec.validation` | Responsibility |
| --- | --- |
| `spec` | Ordered, fail-fast topic coordination |
| `context` | Shared declaration indexes and compact dataset/action locations |
| `dataset` | Dataset identity and order-dimension checks and iteration |
| `dimensions` | Parent, cycle, and entity-dimension checks and iteration |
| `functions` | Function contracts and function iteration |
| `bindings` | Argument validation, nested selector iteration, and selector types |
| `action_outputs` | Output declarations, ownership, producer uniqueness, and coverage |
| `action_inputs` | Input feature and structural-reference checks |
| `collapse_inputs` | Collapse source discovery and source-scope checks |
| `row_context` | Row-context resources and input-order/dimension checks |
| `action_contracts` | Dataframe resources and kind-specific mapping checks |
| `dependencies` | Calculation/write scope and action-cycle checks |
| `errors` | Structured validation errors |

The shared context retains declaration candidates and feature ownership indexes
without raising semantic errors during preparation. Topic modules own the
domain-specific iterators and local calculations their rules need. Each
validation call builds fresh indexes, so revalidating an edited document sees
the current declarations.

`DatasetLocation` represents dataset declarations, feature owners, and inferred
collapse sources; separate `FeatureOwner` wrappers are not needed. Feature
occurrence order is retained independently of dataset order.
`ActionLocation` composes a `DatasetLocation`, retaining both dictionary-key
binding paths and model-ID contract paths without copying its entity and dataset.
`ActionFacts` derives entity dimensions and local features from that shared
location instead of storing repeated copies for every action. Domain resource
records are intentionally small: for example, dataframe checks carry their
action, dataframe arguments, and collapse source, while rules calculate
dataset sets and dimensional conditions locally. Specification models remain
Pydantic models.

Each phase checks one declaration's invariants before advancing to the next.
Output coverage is checked after all actions in a dataset, and declared
features without producers generate warnings rather than errors. Dataframe
arguments precede kind-specific relationships. Iterators apply checks in
document order to datasets, actions, and binding arguments. Vectorize and write
share local dataset checks; conform and expand share join-input checks.

Escape actions require explicit, nonempty feature input and output lists.
Their references participate in normal ownership, producer, unknown-reference,
and cycle checks, and may connect features across datasets. Binding arguments
are still validated, including any explicitly bound dataframe references, but
escape does not receive the dataframe relationship checks used by controlled
function kinds. Its declared features need not match Python parameters or return
values. Compilation retains their feature dependencies; execution invokes the
function and ignores its return value without materializing declared outputs.

### Rule-authoring guidance

1. Choose the domain module and existing phase that owns the invariant. A new
   class or phase is not needed for every rule.
2. Keep the shared context limited to declaration indexes and compact location
   types. Put domain-specific preparation beside its rules.
3. Use explicit iterators to apply rules to datasets, actions, and arguments.
   Short loops and local calculations are appropriate; avoid storing derived
   boolean facts that a rule can calculate directly.
4. Keep each rule focused on one condition and return either `None` or its
   diagnostic. The coordinator raises the first diagnostic in its documented
   sequence.
5. Add focused tests for valid inputs and overlapping faults. Preserve exception
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
