# `uptimely example`

Download examples into the default `example/` directory. Use `--dir`, `--ref`,
or `--no-setup` to customize the download. `--output` is an alias for `--dir`:

```console
uptimely example [--dir DIR] [--ref REVISION] [--no-setup]
```

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `--dir DIR`, `--output DIR` | — | `example` | Destination directory. Without `--no-setup`, it must not already exist. Missing parent directories and the destination directory are created. `--output` is an alias for `--dir`. |
| `--ref REVISION` | — | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |
| `--no-setup` | — | Off | Exclude `pyproject.toml`, `README.md`, `init.sh`, and `.devcontainer/`. Allow an existing destination, but do not overwrite files or follow symlinks at or within the destination. |

Example:

```console
uptimely example
uptimely example --dir pump-analytics
uptimely example --dir pump-analytics --ref HEAD
uptimely example --no-setup --dir pump-analytics
```

Conflicts are checked before copying. If a later write fails, some new files
may already have been copied.
