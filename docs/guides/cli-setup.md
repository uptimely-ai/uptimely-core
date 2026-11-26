# CLI setup

The Uptimely CLI installer supports Linux, macOS, and WSL. It installs the
package version matching the latest stable GitHub release for the current user:

```sh
curl -LsSf https://uptimely.ai/core/install.sh | sh
```

Python does not need to be installed beforehand. Restart your terminal, then
check the command:

```sh
uptimely --help
```

## uv and installation locations

[uv](https://docs.astral.sh/uv/) manages Python tools and their environments.
The installer searches for `uv` on `PATH`, then checks `~/.local/bin/uv`. If
neither is available, it installs uv in `~/.local/bin/`. uv supplies Python
3.13 if needed and installs Uptimely in its own isolated environment.

By default, the environment is in `~/.local/share/uv/tools/uptimely-core/`
and the `uptimely` executable is in `~/.local/bin/`. uv configuration and
environment variables can change these locations. Check them with:

```sh
command -v uv
uv tool dir
uv tool dir --bin
```

This tool environment is separate from project environments. Uptimely does not
yet automatically provision a separate runtime for project code dependencies.
For a project-specific Python environment, see
[Python environment setup](python-setup.md).

## PATH

`PATH` is the list of directories the shell searches for commands. The
installer asks uv to add its tool executable directory to your shell
configuration. Restart your terminal to apply the change.

If `uptimely` is still not found, run `uv tool dir --bin` and add the
reported directory to your shell's `PATH`. If `uv` is not found either, check
`~/.local/bin/uv` or add `~/.local/bin` to your `PATH`.

## Update and uninstall

To update Uptimely to the latest stable release, run the installer again:

```sh
curl -LsSf https://uptimely.ai/core/install.sh | sh
```

Remove Uptimely and its tool environment:

```sh
uv tool uninstall uptimely-core
```

Uninstalling Uptimely leaves uv and your project files in place. These commands
apply to the CLI installed as a uv tool, not to an Uptimely package installed
in a project environment.
