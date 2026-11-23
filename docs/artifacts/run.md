# Run artifacts

## Latest-run artifacts

Each run replaces the previous snapshot. Uptimely does not keep run history or
write a run format-version field.

### Files

| Path | Contents |
| --- | --- |
| `artifacts/run/run.json` | Manifest with run status and execution metadata. |
| `artifacts/run/log.jsonl` | Structured execution log. |
| `artifacts/run/preview/<profile>.json` | Saved sample for a profile. |

Failed invocations still produce a run with dataset aliases whose named results
were produced. Invalid configuration or build errors before execution leave the
previous run unchanged.

### Manifest

The manifest records:

- UTC timestamps, execution duration, and overall status
- Build fingerprint and scope, engine settings, and runtime-validation mode
- Per-invocation statuses, timings, and errors
- Profile statistics and preview paths

### Previews

Previews are collected automatically, including for lazy frames, whether or
not `--preview` is used. Lazy queries are limited before collection, but can
still perform expensive upstream work or repeat computation. The preview size
comes from [`engine.preview_rows`](../guides/configuration.md#engine-settings)
or the CLI `--preview` override.

Saved previews do not replace the dataframes returned by the Engine. Exact
full-profile row counts are recorded only for eager frames. Lazy counts are
`null`. Preview failures are recorded separately and do not change execution
status. If a requested console preview is unavailable, the CLI also reports an
error. Execution timing excludes preview collection, artifact publication,
and display.

### Logs

Logs use UTF-8 JSON Lines, with one event per line. Events include a timestamp,
severity, logger, message, optional invocation or profile IDs, and exception
details. Capture follows configured logging levels and includes Python logs
from the execution thread. It does not redirect stdout or stderr, or capture
logs from other threads.

### Data sensitivity

!!! warning

    Saved samples and logs may contain sensitive project data. Parameter
    values and environment variables are not copied into the manifest, but
    functions can still include them in logs or outputs. Keep credentials out
    of engine settings and log messages. Use `data/output/` for intentionally
    retained analytical data. The generated run is a disposable diagnostic
    snapshot.
