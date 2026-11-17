# Saved runs

The optional `run_id` checks that the saved run has not changed since it was
read. Run storage keeps only the latest run, not run history.

For a reading example, see
[Read a saved run](../guides/python-execution.md#read-a-saved-run).

::: uptimely.run.store
    options:
      heading_level: 2
      show_root_heading: false
      members: [RunStore, RunChangedError, RunNotFoundError]

::: uptimely.run.models
    options:
      heading_level: 2
      show_root_heading: false
      members: [RunManifest, ProfilePreview]
