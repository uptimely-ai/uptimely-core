# Execution results

`datasets` contains the final dataframe for each profile.
`calculated_outputs` contains feature outputs, keyed by profile and feature ID.
`invocation_statuses`, `durations`, and `failures` describe each executed step.
`preview_frames` holds collected samples; `preview_failures` reports previews
that could not be made.

A successful invocation is marked succeeded, a failed invocation is marked
failed, and work that did not run after a failure is marked skipped.

::: uptimely.engine.runtime.result
    options:
      heading_level: 2
      show_root_heading: false
      members: [ExecutionResult]
