# YAML specification authoring

A YAML specification describes a workflow without requiring the full
[Spec JSON format](../artifacts/spec-index.md). Uptimely translates it into
that format during the build. Calculations remain Python functions. The
example project's `spec/` directory contains a complete YAML specification.

Select a YAML file or directory with `uptimely build --yaml-spec PATH`, or set
`application.yaml_spec` in `uptimely.toml`. Paths are relative to the project
root unless absolute. The default source discovery also finds YAML files under
`spec/`. Python and JSON sources remain available.

## Files and directories

A single YAML file contains the entire Spec as a mapping. A directory can
split it into fragments. Each directory name and YAML file stem becomes a Spec
object key. `index.yaml` or `index.yml` is different: its mapping contributes
to its containing directory without adding an `index` key.

For example:

```text
spec/
├── index.yaml
├── dimensions.yaml
├── functions.yaml  # optional explicit function contracts
└── profiles/
    ├── pump.yaml
    └── pump/
        └── features.yaml
```

`index.yaml` can hold root fields such as `name`. `dimensions.yaml` contributes
the `dimensions` mapping. `profiles/pump.yaml` contributes `profiles.pump`,
and `profiles/pump/features.yaml` contributes `profiles.pump.features`.

Objects from different files merge recursively. Identical values can overlap.
Conflicting values are errors with their Spec path and source files. Arrays
are whole values, not concatenated. Validation runs on the combined document,
so a fragment need not be a valid Spec by itself. Index files are processed
first, followed by other files in path order.

Both `.yaml` and `.yml` extensions are supported. `index` is reserved for
directory-level fields. Put a resource named `index` in a surrounding mapping
instead of naming its file `index.yaml`.

## Profiles and operators

The following profile aggregates a feature from another profile. The complete
example includes the referenced dimensions, input profile, and function.

```yaml
name: Telemetry by Hour
seed: aggregate_telemetry
grain: [machine_dimension.machine, machine_timestamp.hour]
assembly:
  aggregate_telemetry:
    function: pump_analytics:aggregate
    args:
      aggregations:
        "$input.bearing_temperature": max
      dimensions: [pump_id, hour]
      rename:
        bearing_temperature: "$output.bearing_temperature_hour_max"
```

Grain and relations accept `dimension.resolution` strings. An order string uses
the same form and means ascending order. Use the full object form for
descending order.

`function` names an importable Python entrypoint in `module:qualified_name`
form. The build uses the callable's annotations, Uptimely function metadata,
and bound argument values to form its function contract, as in Python
authoring. Functions with ambiguous return annotations need an explicit
contract. Declare one under `functions` and use its key as the function name.
Different bindings of the same function must have compatible contracts.

`$input.<feature>` identifies an input feature. It works as an argument value
or a mapping key, as in `aggregations` above. A mapping key passes the feature
ID to the function. `$output.<feature>` identifies an output feature in an
argument value. Uptimely derives the operator's feature interface from these
references and creates output feature declarations when needed. Add feature
metadata under `features` when you need descriptions, types, or units.

Use `inputs` or `outputs` to provide complete explicit lists when dependencies
or outputs cannot be inferred from argument references. For example, a
workflow that reads files internally can declare the features it depends on.
An explicit list replaces inference for that side of the interface.

Uptimely infers the dataframe argument from the input features' owning
profile. Every non-key input feature must belong uniquely to the same profile.
This works across files and includes inferred outputs, regardless of declaration
order. The function must have one identifiable dataframe argument, using its
annotations or explicit function contract.

If there are no non-key input features, the owners are missing or ambiguous,
or the function's dataframe argument cannot be identified, bind the dataframe
in `args` explicitly. For example:

```yaml
args:
  dataset: "$profiles.pump_telemetry.dataset"
```

Use `"$profiles.@.dataset"` for the current profile. Explicit `input` bindings
also remain supported, with `input: '@'` selecting the current profile.

Set `merge: default` to merge a fragment by grain. For a custom merge, use
`merge` with its `function` and `args`. `row_context` uses the same fields as
the Spec JSON operator. Full JSON-shaped operator declarations also remain
supported.

## Values and references

The loader uses YAML 1.2 safe parsing and rejects duplicate mapping keys,
non-string keys, non-finite numbers, recursive aliases, and values outside the
JSON data model. Quote dates that should be strings. YAML anchors and aliases
work within one file, not across files.

Use the existing [Spec selectors](../artifacts/spec-selectors.md) for other
references, including datasets, parameters, and paths. Selectors are
interpreted by Uptimely, not by YAML. Runtime configuration remains in
`uptimely.toml`.

Python code can load a YAML source with
`uptimely.spec.yaml.load_spec(path)`. The returned document uses the same
models and semantic validation as a JSON Spec. Function entrypoints must be
importable when concise operators are loaded. Loading them imports Python
modules, so only load trusted project code.
