The demo site is available here: [Pump Analytics](../example/index.html)

It is created from the repository's [pump analytics example](https://github.com/uptimely-ai/uptimely-core/tree/main/example).

The Explorer is a static frontend backed by the project's generated snapshot.
Build and preview it locally, or export the same frontend and data for hosting:

```console
$ uptimely examples
$ uptimely build example
$ uptimely run example --preview 10 --log-level debug
$ uptimely explore example
$ uptimely explorer export example --output docs/example
```

The GitHub Pages pipeline builds and runs this example before exporting it.
The static export includes run information, debug logs, and up to ten preview
rows per profile; no running API server is needed to view the results.
