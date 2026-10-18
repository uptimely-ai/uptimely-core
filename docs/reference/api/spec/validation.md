# Spec validation

`uptimely.spec.validation` exports semantic validation functions and the
structured `SpecError` exception. For normal loading and authoring, use
[load_spec, from_python, or prepare_spec](api.md), which perform the
required validation for you.

The sections below document the exported interfaces in their defining modules,
not the internal rule helpers.

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

`uptimely.spec.validation.spec` validates document references and
relationships after structural parsing.

::: uptimely.spec.validation.spec
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_spec]

## dimensions

`uptimely.spec.validation.dimensions` exposes a check for globally unique
dataset identifiers.

::: uptimely.spec.validation.dimensions
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_dataset_ids]

## prepared

`uptimely.spec.validation.prepared` validates resolved functions and calls.

::: uptimely.spec.validation.prepared
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_prepared]

</div>
