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

Enable per-step runtime checks with `--validate`, or use `--build` to publish
a fresh build before running:

```console
uptimely run example --validate
uptimely run example --validate --log-level debug
uptimely run example --build
```

See [Validate execution](runtime-validation.md) for optional and always-on checks.

If the project uses a non-default source directory, pass the same `--src-path`
to both the build and each run that imports its local modules.

See [Inspect logs and diagnose failures](logging.md) for logging behavior.
