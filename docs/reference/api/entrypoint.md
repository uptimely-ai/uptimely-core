# Python entrypoints

`uptimely.entrypoint` loads Python callables and inspects their annotated
signatures. Entry points use `module:function` syntax and can refer to an
importable module, a local Python file, an HTTPS URL, or an S3 URI.

!!! warning "Only load trusted code"

    Both loading a callable and reading its signature import and execute the
    referenced Python module. S3 access requires the `uptimely-core[s3]` extra.

<div class="api-reference" markdown="1">

## entrypoint

::: uptimely.entrypoint
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - FunctionSignature
        - load_callable
        - read_signature
        - type_name
        - REMOTE_SCHEMES
        - REMOTE_READ_TIMEOUT

</div>
