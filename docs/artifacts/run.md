# Run artifacts

## Results and previews

See [Execution results](../python/engine-results.md) for the Engine's returned
dataframes and per-invocation results, and
[Execution options](../guides/build-and-run.md#execution-options)
for displaying saved samples from the CLI.

## Latest-run artifacts

Every execution saves `artifacts/run/run.json`, `log.jsonl`, and
`preview/<profile>.json`. This replaces the previous run completely, including
previews for profiles that no longer appear. There is no run history or run
format-version field.

The manifest records UTC timestamps, execution duration, overall status, build
fingerprint and scope, engine settings, runtime-validation mode, per-invocation
statuses/timings/errors, and profile statistics and preview paths. Failed
invocations still produce a saved run with any available partial profile
results. Invalid configuration or build errors before execution do not
replace the previous run.

Previews are collected automatically, including for lazy frames, even without
`--preview`. Lazy queries are limited before collection, but this may still
perform expensive upstream work or repeat computation.
The preview size comes from
[`engine.preview_rows`](../reference/configuration.md#engine-settings) or the CLI `--preview` override.
Previews do not replace the dataframes returned by the Engine.
Execution timing excludes preview collection, artifact publication, and display.
Exact full-profile row counts are recorded
only for eager frames. Lazy counts are `null`. Preview failures are recorded
separately and do not change the execution status. When console previews are
requested, an unavailable preview is also reported as a CLI error.

Logs use UTF-8 JSON Lines: one event per line with timestamp, severity, logger,
message, optional invocation/profile IDs, and exception details. Capture follows
configured logging levels and includes Python logs from the execution thread.
It does not redirect stdout/stderr or capture other threads' logs.

Saved samples and logs may contain sensitive project data. Parameter values
and environment variables are not copied into the manifest, but functions can
still include them in logs or outputs. Keep credentials out of engine settings
and log messages. Use `data/output/` for intentionally retained analytical data.
The generated run is a disposable diagnostic snapshot.
