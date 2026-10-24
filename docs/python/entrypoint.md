# Python entrypoints

`uptimely.entrypoint` loads Python callables and inspects their annotated
signatures. Entry points use `module:function` syntax and can refer to an
importable module, a local Python file, an HTTPS URL, or an S3 URI.

Use `Entrypoint` to access the function and module. Load the callable with
`entrypoint.function.load()` and inspect its annotations with
`entrypoint.function.signature`.

Read `entrypoint.module.source_file` to get the loaded module's file path, or
its source URI for HTTPS and S3 entrypoints. Modules without a file raise
`ValueError`.

!!! warning "Only load trusted code"

    Loading a callable, reading its signature, and accessing `module.source_file`
    import and execute the referenced Python module if it is not already loaded.
    S3 access requires the `uptimely-core[s3]` extra.

<div class="api-reference" markdown="1">

## entrypoint

::: uptimely.entrypoint
    options:
      heading_level: 3
      show_root_heading: false
      members:
        - Entrypoint
        - Module
        - Function
        - Signature
        - TypeAnnotation
        - REMOTE_SCHEMES
        - REMOTE_READ_TIMEOUT

</div>
