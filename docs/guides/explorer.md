# Inspect results in Explorer

## View a project

A successful build bundle is required to show the Spec and execution plan.
Build and start the Explorer in one command:

```console
uptimely explore example --build
```

Open <http://127.0.0.1:8001/>

An Engine run is required to show data
previews, logs, and run information:

```console
uptimely run example
```

## Export a static site

Build the project and run it before exporting to include run information:

```console
uptimely export example --output docs/example
```

!!! info

    The full Explorer will continue to gain interactive capabilities. Static
    exports may differ from the locally served website as those capabilities
    evolve.

See [`uptimely explore`](../reference/cli/explorer.md) for serving and
[`uptimely export`](../reference/cli/export.md) for static exports, and the
[Explorer API reference](../reference/python/explorer.md) for presentation data.

## Example

```console
uptimely build example
uptimely run example --preview 10 --log-level debug
uptimely export example --output docs/example
uptimely export example --output cooling-pump-analytics-explorer.zip
```

Export includes the complete saved log and bounded previews. These artifacts may
contain sensitive data. Review them before publishing, and re-export after
running the project to update the hosted results. Invalid or incomplete saved
run artifacts cause export to fail rather than silently omit results.
