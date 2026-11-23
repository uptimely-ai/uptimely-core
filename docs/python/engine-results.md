# Execution results

`datasets` contains available final dataset aliases. On failure, an alias is
present only if its named result was produced.
`calculated_outputs` is `None` because feature output summaries are not yet
available.
`invocation_statuses`, `durations`, and `failures` describe each executed step.
`preview_frames` holds collected samples, and `preview_failures` reports previews
that could not be made.

A successful invocation is marked succeeded, a failed invocation is marked
failed, and work that did not run after a failure is marked skipped.

::: uptimely.engine.runtime.result
    options:
      heading_level: 2
      show_root_heading: false
      members: [ExecutionResult]
