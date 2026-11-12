# `uptimely examples`

Run `uptimely examples` to download examples into the default `examples/`
directory. Use `--output` or `--ref` to customize the download:

```console
uptimely examples [--output PATH] [--ref REVISION]
```

The explicit `uptimely examples download` form accepts the same options.

## `examples download`

Download the examples directory from the public GitHub repository:

```console
uptimely examples download [--output PATH] [--ref REVISION]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--output PATH` | No | `examples` | Destination directory. The destination must not already exist. Missing parent directories and the destination directory are created. |
| `--ref REVISION` | No | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |

Example:

```console
uptimely examples
uptimely examples download --output examples --ref HEAD
```
