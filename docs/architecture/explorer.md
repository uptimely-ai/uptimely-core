# Explorer

The Explorer presents a project's build bundle and run output for inspection.
It does not execute analytical functions.

![Uptimely Core Demo](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-feature-lineage.png)

## View a project

A successful build bundle is required to show the Spec and execution plan.
Build and start the Explorer in one command:

```console
uptimely explore examples/pump_analytics --build
```

Open <http://127.0.0.1:8001/>

An Engine run is required to show data
previews, logs, and run information:

```console
uptimely run examples/pump_analytics
```

## Export a static site

Build the project and run it before exporting to include run information:

```console
uptimely explorer export examples/pump_analytics --output docs/examples/pump_analytics
```

!!! info

    The full Explorer will continue to gain interactive capabilities. Static
    exports may differ from the locally served website as those capabilities
    evolve.

See the [Explorer CLI reference](../cli/explorer.md) for serving and export
options, and the [Explorer API reference](../python/explorer.md) for
presentation data.
