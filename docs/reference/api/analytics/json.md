# Analytics JSON

`uptimely.analytics.json` reads and writes analytics documents as JSON. Use
[load_analytics](api.md#uptimely.analytics.api.load_analytics) when loading a
document that also needs semantic validation.

<div class="api-reference" markdown="1">

## codec

`uptimely.analytics.json.codec` reads JSON, converts document models to
dictionaries, and writes analytics documents. `load_document` reads document
data; it does not perform the semantic validation provided by `load_analytics`.

::: uptimely.analytics.json.codec
    options:
      heading_level: 3
      show_root_heading: false
      members: [load_document, to_document, write_document]

</div>
