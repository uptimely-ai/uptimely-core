# Explorer demo

[Open the Explorer demo](../example/index.html){ .md-button .md-button--primary }

It is created from the repository's [data-center cooling pump example](https://github.com/uptimely-ai/uptimely-core/tree/main/example).

The Explorer is a static frontend backed by the project's generated snapshot.
For the full local setup and workflow, follow the
[cooling-pump example tutorial](tutorial.md). To build and export a local
Explorer snapshot from the repository root:

```console
$ uvx --from uptimely-core uptimely example --dir pump-analytics
$ cd pump-analytics
$ uv sync
$ uv run uptimely build
$ uv run uptimely run --preview 10 --log-level debug
$ uv run uptimely explorer export . --output ../docs/example
$ uv run uptimely explore
```

The GitHub Pages pipeline builds and runs this example before exporting it.
The static export includes run information, debug logs, and up to ten preview
rows per profile; no running API server is needed to view the results.
