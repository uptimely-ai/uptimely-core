# Analytics validation

`uptimely.analytics.validation` exports semantic validation functions and the
structured `AnalyticsError` exception. For normal loading and authoring, use
[load_analytics, from_python, or prepare_analytics](api.md), which perform the
required validation for you.

The sections below document the exported interfaces in their defining modules,
not the internal rule helpers.

<div class="api-reference" markdown="1">

## errors

`uptimely.analytics.validation.errors` defines validation errors with a code
and document path.

::: uptimely.analytics.validation.errors
    options:
      heading_level: 3
      show_root_heading: false
      members: [AnalyticsError]

## analytics

`uptimely.analytics.validation.analytics` validates document references and
relationships after structural parsing.

::: uptimely.analytics.validation.analytics
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_analytics]

## dimensions

`uptimely.analytics.validation.dimensions` exposes a check for globally unique
dataset identifiers.

::: uptimely.analytics.validation.dimensions
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_dataset_ids]

## prepared

`uptimely.analytics.validation.prepared` validates resolved functions and calls.

::: uptimely.analytics.validation.prepared
    options:
      heading_level: 3
      show_root_heading: false
      members: [validate_prepared]

</div>
