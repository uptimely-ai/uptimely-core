The demo site is available here: [Data-center Cooling Pump Analytics](../example/index.html)

It is created from the repository's [data-center cooling pump example](https://github.com/uptimely-ai/uptimely-core/tree/main/example).

The Explorer is a static frontend backed by the project's generated snapshot.
Build and preview it locally, or export the same frontend and data for hosting:

```console
$ uptimely example --dir pump-analytics
$ uptimely build pump-analytics
$ uptimely run pump-analytics --preview 10 --log-level debug
$ uptimely explore pump-analytics
$ uptimely explorer export pump-analytics --output docs/example
```

The GitHub Pages pipeline builds and runs this example before exporting it.
The static export includes run information, debug logs, and up to ten preview
rows per profile; no running API server is needed to view the results.
