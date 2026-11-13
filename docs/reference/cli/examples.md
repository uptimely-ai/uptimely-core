# `uptimely example`

Run `uptimely example` to download examples into the default `example/`
directory. Use `--output` or `--ref` to customize the download:

```console
uptimely example [--output PATH] [--ref REVISION]
```

The explicit `uptimely example download` form accepts the same options.

## `example download`

Download the example directory from the public GitHub repository:

```console
uptimely example download [--output PATH] [--ref REVISION]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--output PATH` | No | `example` | Destination directory. The destination must not already exist. Missing parent directories and the destination directory are created. |
| `--ref REVISION` | No | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |

Example:

```console
uptimely example
uptimely example download --output example --ref HEAD
```
