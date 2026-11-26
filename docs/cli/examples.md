# `uptimely example`

Download the full example project into the current working directory. Existing
files are preserved, and the command stops if an example file would overwrite
one. Use `--dir` or `--ref` to customize the download. `--output` is an alias
for `--dir`:

```console
uptimely example [--dir DIR] [--ref REVISION]
```

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `--dir DIR`, `--output DIR` | — | `.` | Destination directory. By default, files are merged into the current directory without overwriting existing files. A different destination must not already exist. Missing parent directories and the destination directory are created. `--output` is an alias for `--dir`. |
| `--ref REVISION` | — | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |

Example:

```console
uptimely example
uptimely example --dir pump-analytics
uptimely example --dir pump-analytics --ref HEAD
```

The downloaded project includes its README, initialization script, and Dev
Container configuration.
