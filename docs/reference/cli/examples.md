# `uptimely example`

Run `uptimely example` to download examples into the default `example/`
directory. Use `--dir` or `--ref` to customize the download. `--output` is an
alias for `--dir`:

```console
uptimely example [--dir DIR] [--ref REVISION]
```

The explicit `uptimely example download` form accepts the same options.

## `example download`

Download the example directory from the public GitHub repository:

```console
uptimely example download [--dir DIR] [--ref REVISION]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--dir DIR` | No | `example` | Destination directory. The destination must not already exist. Missing parent directories and the destination directory are created. `--output` is an alias. |
| `--ref REVISION` | No | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |

Example:

```console
uptimely example
uptimely example --dir pump-analytics
uptimely example download --dir pump-analytics --ref HEAD
```
