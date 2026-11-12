# Spec serialization

`uptimely.spec.serialization` reads and writes Spec documents as JSON. Use
[load_spec](api.md#uptimely.spec.api.load_spec) to also check the declarations.

<div class="api-reference" markdown="1">

## serialization

`load_document` reads JSON without checking that the declarations work
together. `load_spec` performs those checks when it loads the document.

::: uptimely.spec.serialization
    options:
      heading_level: 3
      show_root_heading: false
      members: [load_document, to_document, write_document]

</div>
