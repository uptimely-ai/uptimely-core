# Preview run results

After a successful run, Uptimely can display a sample of each final profile.
Previews show all columns and omit the Polars shape line. They appear after the
completion and processed-profile summaries, before any debug details.

Run `uptimely run --preview [ROWS]` to set the preview row limit and display the
results. A bare `--preview` uses the configured `engine.preview_rows` value,
which defaults to 5. Without `--preview`, previews are saved but not shown in
the console. Console output reuses the saved sample instead of executing a lazy
query again.

Previews, the completion summary, and processed-profile details are hidden at
log levels above `info`.

Materialized results from an engine run:

![Uptimely run preview](https://uptimely-public.s3.pl-waw.scw.cloud/uptimely-demo/uptimely-core/uptimely-core-run-preview.png)

See the [`uptimely run` reference](../cli/engine.md) for command options and
[Run artifacts](../artifacts/run.md#latest-run-artifacts) for details about
preview collection and query costs.
