# `uptimely example`

Download the full example project into the default `example/` directory. Use
`--dir` or `--ref` to customize the download. `--output` is an alias for `--dir`:

```console
uptimely example [--dir DIR] [--ref REVISION]
```

| Option | TOML setting | Default | Purpose |
| --- | --- | --- | --- |
| `--dir DIR`, `--output DIR` | — | `example` | Destination directory. It must not already exist. Missing parent directories and the destination directory are created. `--output` is an alias for `--dir`. |
| `--ref REVISION` | — | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |

Example:

```console
uptimely example
uptimely example --dir pump-analytics
uptimely example --dir pump-analytics --ref HEAD
```

The downloaded project includes its README, initialization script, and Dev
Container configuration.
