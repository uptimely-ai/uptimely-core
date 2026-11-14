# `uptimely example`

Run `uptimely example` to download examples into the default `example/`
directory. Use `--dir`, `--ref`, or `--no-setup` to customize the download.
`--output` is an alias for `--dir`:

```console
uptimely example [--dir DIR] [--ref REVISION] [--no-setup]
```

The explicit `uptimely example download` form accepts the same options.

## `example download`

Download the example directory from the public GitHub repository:

```console
uptimely example download [--dir DIR] [--ref REVISION] [--no-setup]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--dir DIR` | No | `example` | Destination directory. Without `--no-setup`, it must not already exist. Missing parent directories and the destination directory are created. `--output` is an alias. |
| `--ref REVISION` | No | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |
| `--no-setup` | No | Off | Exclude `pyproject.toml`, `README.md`, `init.sh`, and `.devcontainer/`. Allow an existing destination, but do not overwrite files or follow symlinks at or within the destination. |

Example:

```console
uptimely example
uptimely example --dir pump-analytics
uptimely example download --dir pump-analytics --ref HEAD
uptimely example --no-setup --dir pump-analytics
```

Conflicts are checked before copying. If a later write fails, some new files
may already have been copied.
