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

## Execution options

For example, preview the configured number of rows per profile, or request a
specific row limit:

```console
uptimely run example
uptimely run --preview
uptimely run --preview 10
```

Use `uptimely build` to change the execution plan or feature scope. By default,
Engine executes the saved build without compiling or rebuilding it.
`--build` rebuilds from the project's discovered spec source before execution.
The CLI always checks saved-build integrity, configuration, and backend
compatibility. Per-step runtime validation is opt-in:

```console
uptimely run example --validate
uptimely run example --validate --log-level debug
uptimely run example --build
```

If the project uses a non-default source directory, pass the same `--src-path`
to both the build and each run that imports its local modules.

See [Inspect logs and diagnose failures](logging.md) for logging behavior.
