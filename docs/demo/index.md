The demo site is available here: [Pump Analytics](../examples/pump_analytics/index.html)

It is created from the repository's [pump analytics example](https://github.com/uptimely-ai/uptimely-core/tree/main/examples/pump_analytics).

The Explorer is a static frontend backed by the project's generated snapshot.
Build and preview it locally, or export the same frontend and data for hosting:

```console
$ uptimely examples
$ uptimely build examples/pump_analytics
$ uptimely run examples/pump_analytics --preview 10 --log-level debug
$ uptimely explore examples/pump_analytics
$ uptimely explorer export examples/pump_analytics --output docs/examples/pump_analytics
```

The GitHub Pages pipeline builds and runs this example before exporting it.
The static export includes run information, debug logs, and up to ten preview
rows per profile; no running API server is needed to view the results.
