# Build and run analytics

## Typical workflow

From an installed package, download examples and build the complete active
bundle, including its spec, execution plan, and Explorer data snapshot:

```console
uptimely example --dir pump-analytics
uptimely build pump-analytics
```

Run the saved execution plan from the active build:

```console
uptimely run pump-analytics
```

The command defaults and options are documented on each command page. Project
build consumers use the active bundle under `artifacts/build/`. Rebuild it
with `uptimely build` to change the saved plan or feature scope. The
`uptimely-mcp` server is a separate optional command. See
[MCP API](ai/setup.md) for installation and client setup.
