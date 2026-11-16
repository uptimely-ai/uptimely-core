# Run artifacts

## Results and previews

The Engine returns final profile dataframes, calculated feature outputs,
per-invocation statuses and durations, failures, and the plan version. A
successful invocation is marked succeeded, a failed invocation is marked
failed, and work that did not run after a failure is marked skipped.

Each run replaces the latest diagnostic snapshot in `artifacts/run/`.
It includes run metadata, logs, and a bounded preview for each available
profile. The default preview is five rows. Previews are collected after
execution, including from lazy frames, and do not replace the dataframes
returned by the Engine. Preview failures are reported separately and do not
change the invocation status. Preview collection is outside the reported
execution duration.

Use the CLI `--preview` option to also display these samples after a successful
run. The saved previews are produced even when console display is not
requested.

The generated run directory is a latest-run snapshot, not an output store or
run history. Use a project's data output location for results intended to be
retained. Review logs and previews before sharing because they may contain
project data.

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
perform expensive upstream work. Exact full-profile row counts are recorded
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
