# Python authoring

Use `import uptimely as up` for Python authoring declarations and `up.ref` for
deferred references. These declarations convert to the
[spec document model](spec/model.md). Their defining modules remain available
under `uptimely.spec.python`; the reference sections below follow those modules.

For a runnable example, see the
[analytics project structure](../project-layout/project-structure.md).

## Build-time declarations and runtime configuration

Python declarations define the build-time workflow. Operators, bindings, and
profile grain are compiled into the plan, so changes to them require a rebuild.
Runtime parameters, source/sink locations, and validation controls normally
change execution without changing the graph.

| Setting | Ownership | Rebuild required? |
| --- | --- | --- |
| Operators, bindings, and profile grain | Build-time declarations | Yes |
| Runtime parameters, source/sink locations, and validation controls | Project/runtime configuration and run options | Normally no |

Runtime parameters can change calculation results without changing the plan.
The plan's required backend is fixed at build time; an incompatible backend
setting fails rather than reinterpreting the plan.

## Declarative profiles

```python
import polars as pl
import uptimely as up

machine = up.Dimension(
    id="machine",
    resolutions=[up.Resolution(id="machine", key="machine", type="string")],
)


@up.function(kind="collapse")
def maximum(
    dataset: pl.LazyFrame, feature: str, dimensions: list[str], output: str
) -> pl.LazyFrame: ...


class PumpFeatures(up.FeatureSet):
    bearing_temperature_max = up.Feature(
        id="bearing_temperature_max",
        type="float",
        unit="C",
        description="Maximum observed bearing temperature.",
    )


class Pump(up.Profile):
    id = "pump_summary"
    name = "Pump Summary"
    description = "Maximum bearing temperature per pump."
    grain = [up.Grain(machine, "machine")]
    features = PumpFeatures()

    assembly = [
        up.Operator(
            id="temperature_max",
            interface=up.Interface(
                outputs=[features.bearing_temperature_max],
            ),
            compute=up.Binding(
                function=maximum,
                arguments=dict(
                    dataset=up.ref.data("telemetry"),
                    feature=up.ref.feature("bearing_temperature"),
                    dimensions=up.ref.profile().grain.ids,
                    output=up.ref.feature("bearing_temperature_max"),
                ),
            ),
        ),
    ]
```

`Feature.id` is the stable feature identifier used by references and serialized
keys. `Feature.name` is an optional display label; when omitted, it is generated
by humanizing the ID (for example, `bearing_temperature_max` becomes
`Bearing Temperature Max`). A `FeatureSet` subclass groups a profile's
feature declarations as attributes, which operators reference in their outputs
instead of repeating metadata inline.

```python
python_spec = up.Spec(
    profiles=[Pump],
    name="Pump analytics",
)
```

Root-level `Spec`, `Profile`, `Operator`, `Interface`, `Binding`,
`Dimension`, `Resolution`, `Grain`, `Feature` and `FeatureSet` are Python
authoring classes.
Document-model classes remain under `uptimely.spec.model` and the existing
`uptimely.spec` exports. The authoring `Spec` is defined as
`uptimely.spec.python.spec.Spec` and exported as `up.Spec` and
`uptimely.spec.python.Spec`.

Dimensions have stable IDs and declare one or more keyed resolutions. A profile's
`grain` selects one resolution per dimension; the selected resolution's key is
the dataframe column used by that profile. Optional dimension names are
human-readable labels generated from IDs when omitted.

`up.Spec` accepts the profile declarations only. It infers dimension and
resolution definitions from each profile's grain, requires repeated declarations
to agree, rejects unresolved resolutions and conflicting metadata, and emits
deterministic output. Profile IDs are globally unique. The function catalog is
collected from the registered profiles; reference resolution does not mutate
the supplied declarations. `ProfileRegistry([Pump]).to_declarations()` can
instantiate and register profile classes.

`Operator` declares work without executing it. It takes an `id`, an `interface`,
and a `compute` binding. `Binding` contains the implementation `function` and
named `arguments`; `Interface` contains feature `inputs` and `outputs`.
Interface inputs are optional: if omitted, feature references in compute
and optional merge arguments are inferred as dependencies, excluding declared
outputs and retaining first-occurrence order. If supplied, they define the
dependencies instead; an empty input list disables inference. `Interface`
validates feature references and rejects repeated input or output IDs when
constructed. It checks them again during conversion, so later mutations of its
collections cannot bypass those checks.

`Binding` owns function metadata (`kind` and `reference`), callable argument
validation (`bound_arguments()`), and conversion (`to_model()` and
`to_function_template()`). `Interface.to_model(compute=..., merge=...)` accepts
canonical bindings and builds feature selectors. `Operator` coordinates these
conversions and validates compute/merge compatibility; its existing metadata
properties and `bound_arguments()` delegate to the compute binding.
Entrypoint strings and function references are not imported during these
conversions; their signature checks are deferred until compilation.

`Operator` also accepts an optional `row_context`
requirement. Its function catalog ID is derived from the referenced function
name. Optionally annotate callable implementations with `@function(kind=...)`.
The decorator attaches
semantic metadata for validation;
it returns the original function without wrapping or executing it. Alternatively,
keep implementations undecorated and supply their contract through
`ref.function(implementation, kind=...)`. Entrypoint strings also use explicit
function references. Kind belongs to the function, not the operator.

An explicit reference kind must agree with decorated metadata. References to
decorated callables inherit their kind when it is omitted. Decoration is
optional, but a function kind is still required to build an executable operator;
Uptimely never guesses a producer's kind from its signature or collection.
Implementations aren't called during authoring; assembly checks callable
parameter names and required arguments.

```python
from uptimely.spec.python import function, ref


@function(kind="collapse")
def maximum(dataset, feature, dimensions, output): ...


decorated = ref.function(maximum)  # Carries the declared collapse contract.
external = ref.function("third_party.analytics:maximum", kind="collapse")
```
`read` functions take no dataframe arguments. `conform`, `collapse`, and
`expand` each take only their foreign/source dataframe; the engine supplies and
reconciles the target profile separately. `conform` sources and targets have
the same grain. `collapse` moves to a coarser grain, and `expand` moves to a
finer grain; parent links between resolutions describe valid coarsening and
refinement.
Declare dimensional matching keys explicitly with
`ref.profile().grain.ids` (or a named profile's `.grain.ids` selector).
Grouping and ordering references do not implicitly select matching keys.
Fragment-producing functions (`read`, `conform`, `expand`, and `collapse`)
return Polars `DataFrame` or `LazyFrame` fragments; other dataframe types and
custom adapters are not currently supported. The engine assembles fragments
for the same profile by complete keys with a full outer join, preserving
partial coverage while rejecting duplicate keys and feature collisions. An
`expand` fragment may omit dimension keys its lower-dimensional source cannot
supply; the engine left-joins such a fragment onto the accumulated profile frame by
the keys it carries, broadcasting a dimensionless fragment to every
observation. See the runnable
[dimensional operations example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/dimensional_operations)
and [engine fragment contract](../components/engine.md#fragments).

`vectorize` functions instead receive the accumulated target dataframe and
return that complete dataframe enriched with their declared outputs. They must
preserve existing columns and values, row count, key identities, and row order;
they do not return fragments and cannot declare a merge binding. The engine
always checks the returned schema, while opt-in runtime validation checks
preservation of existing values and row order. Functions must not mutate their
input dataframes: publishing by assignment cannot roll back mutations made by
user code.

Fragment-producing operators without an explicit `merge` binding use the
builtin merge-by-grain function. A custom merge binding overrides the default.
Changing an operator's merge binding requires rebuilding the project.
The implementation module's package must be installed in the build and runtime
environments; install a local project package in editable mode for development.

References such as `ref.feature("result").id` pass an identifier, not feature
data, and may be used for output-name arguments. Declare produced features in
`interface.outputs`; they are not inferred from arguments. In the resulting
spec document, dependencies are recorded explicitly in `interface.inputs`.
Writes use `interface=Interface(outputs=[])`. For
generated declarations, use `Profile(id=..., grain=[...], assembly=[...])`.

### Profile assembly

Each profile declares its work in one `assembly` list. For readability, a
mapping of group names to operator lists is also accepted and flattened in
insertion order:

```python
assembly = {
    "ingestion": [read_operator],
    "calculations": [calculate_operator],
    "publishing": [write_operator],
}
```

Groups are organizational only; function kind remains explicit on functions
or function references and determines runtime behavior. Operator IDs must be
non-empty and unique within the profile. Reusing one function in multiple
operators is allowed with distinct operator IDs; its function name identifies
the reusable catalog contract.

The assembly defaults to an empty list and is copied for each profile instance.
Constructor arguments replace the class declaration, including when an empty
list is passed. Subclasses inherit assembly using normal Python attribute lookup:
defining `assembly` replaces the inherited list rather than merging it. To extend
it, write `assembly = [*Base.assembly, another_operator]`.

List order and group order do not impose execution order. Declared feature
dependencies determine scheduling. Uptimely does not inspect an escape
function's internal steps.

### Migrating from FunctionMapping

- Replace `FunctionMapping(...)` with `Operator(id=..., ...)`. Move named profile
  attributes or entries in `mappings={...}` into the appropriate assembly list.
  Use the former attribute name or dictionary key as the operator ID.
- Replace imports from `uptimely.spec.python.mapping` or
  `uptimely.spec.python.mappings` with `uptimely.spec.python.assembly`, or import
  `Operator` directly from `uptimely.spec.python`.
- Access declarations through `Profile.assembly` rather than `Profile.mappings`.
- Convert an operator with `Operator.to_model()`; its own ID supplies the canonical
  operator identifier. Feature metadata remains in `outputs`, and
  `Feature.to_model()` is unchanged.

Python profiles expose declarations through `Profile.assembly`; canonical
documents and exported JSON use the same `assembly` key.
The current JSON contract is spec version 6. JSON profiles use an `assembly`
mapping whose operators declare `compute`, optionally `merge`, and `interface`;
see the [spec migration guide](../components/spec.md#migrating-from-spec-version-5).

<div class="api-reference" markdown="1">

## spec

`uptimely.spec.python.spec` groups declarations into a
`up.Spec` definition.

::: uptimely.spec.python.spec
    options:
      heading_level: 3
      show_root_heading: false

## profile

`uptimely.spec.python.profile` declares profile grain, metadata, assembly, and
optional class registries.

::: uptimely.spec.python.profile
    options:
      heading_level: 3
      show_root_heading: false

## dimension

`uptimely.spec.python.dimension` declares shared dimensions.

::: uptimely.spec.python.dimension
    options:
      heading_level: 3
      show_root_heading: false

## feature

`uptimely.spec.python.feature` declares metadata for operator outputs.

::: uptimely.spec.python.feature
    options:
      heading_level: 3
      show_root_heading: false

## assembly module

`uptimely.spec.python.assembly` defines `Operator`, `Interface`, and `Binding`,
the declarations used in a profile's assembly.

::: uptimely.spec.python.assembly
    options:
      heading_level: 3
      show_root_heading: false

## functions

`uptimely.spec.python.functions` defines optional implementation-level semantics.
Import `function` directly from `uptimely.spec.python` for
`@function(kind="...")`, or import the `functions` module for
`@functions.function(kind="...")`. The former `@kind(...)` decorator is removed.
The decorator does not prove implementation behavior; it declares the contract
that Uptimely validates at its supported boundaries.

::: uptimely.spec.python.functions
    options:
      heading_level: 3
      show_root_heading: false

## bind

`uptimely.spec.python.bind` provides lower-level nested argument bindings and
serialization helpers. Operators bind functions directly through their
`function` and `arguments` attributes.

::: uptimely.spec.python.bind
    options:
      heading_level: 3
      show_root_heading: false

## ref

`up.ref` (also available as `uptimely.spec.python.ref`) builds deferred
references to functions and spec objects. It does not construct or load data.

| Helper | Meaning |
| --- | --- |
| `up.ref.data()` | Current profile's dataframe. |
| `up.ref.data("telemetry")` | Named profile's dataframe. |
| `up.ref.fragment()` | Staged fragment for the current operator's merge binding. |
| `up.ref.feature("temperature")` | Input feature column; infers a dependency unless `inputs` is explicit. |
| `up.ref.feature("maximum")` | Identifier of a feature in the containing operator's `outputs`; no input dependency. |

`ref.feature()` does not declare a feature. An undeclared output name raises
`ValueError`, including references nested in lists, dictionaries, and bindings.
Use `ref.profile().data`, `ref.profile(name).data`,
`ref.feature(name)`, and `ref.feature(name).id` to create deferred references.
The general `.id` selector does not require the feature to be an operator output.

Function references accept `validate_signature`, defaulting to `True`.
Conversion preserves it in the function catalog and exported JSON. When
`False`, compilation and documentation do not import the implementation or
inspect its signature. Spec-level contracts and declared feature dependencies
are still validated, and execution still requires a loadable implementation.
When enabled, compilation checks keyword-call compatibility, required
parameters, positional-only parameters, and supported annotation contradictions.
Annotations may be omitted; an explicit incompatible annotation is rejected.

Function references also carry a `description` into the function catalog and
exported JSON. When a callable is referenced, the description defaults to the
summary line of its docstring; pass `description=` to override it. Entrypoint
strings have no default because the implementation is not imported while
loading the spec.

Use an entrypoint string when the implementation must not be imported while
loading the Python spec:

```python
ref.function(
    "other_project.functions:calculate",
    kind="vectorize",
    validate_signature=False,
)
```

Python spec declarations execute during source loading. Do not import an
unavailable analytical implementation from the declaration module itself;
pass its entrypoint as a string instead.

::: uptimely.spec.python.ref
    options:
      heading_level: 3
      show_root_heading: false

## row_context

`uptimely.spec.python.row_context` declares row windows for functions.
The runtime value is documented under [row context](row-context.md).

::: uptimely.spec.python.row_context
    options:
      heading_level: 3
      show_root_heading: false

## conversion

`uptimely.spec.python.conversion` converts declarations to document model
objects. Use [api.from_python](spec/api.md#uptimely.spec.api.from_python)
to convert and semantically validate in one operation.

::: uptimely.spec.python.conversion
    options:
      heading_level: 3
      show_root_heading: false

</div>
