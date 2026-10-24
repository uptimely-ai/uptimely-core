# Spec JSON

`uptimely.spec.json` reads and writes spec documents as JSON. Use
[load_spec](api.md#uptimely.spec.api.load_spec) when loading a
document that also needs semantic validation.

<div class="api-reference" markdown="1">

## codec

`uptimely.spec.json.codec` reads JSON, converts document models to
dictionaries, and writes spec documents. `load_document` reads document
data; it does not perform the semantic validation provided by `load_spec`.

::: uptimely.spec.json.codec
    options:
      heading_level: 3
      show_root_heading: false
      members: [load_document, to_document, write_document]

</div>
