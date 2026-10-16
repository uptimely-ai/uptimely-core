# `uptimely examples`

## `examples download`

Download the examples directory from the public GitHub repository:

```console
uptimely examples download [--output PATH] [--ref REVISION]
```

| Option | Required | Default | Purpose |
| --- | --- | --- | --- |
| `--output PATH` | No | `examples` | Destination directory. The destination must not already exist. |
| `--ref REVISION` | No | Release tag matching the installed package version | Git branch, tag, or commit to download. Use `HEAD` to select the repository's default branch. |

Example:

```console
uptimely examples download --output examples --ref HEAD
```
