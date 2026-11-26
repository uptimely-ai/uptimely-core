# Python environment setup

As an alternative to installing the CLI as a tool, create a Python environment
in a new project directory.

If uv is not installed, [install it](https://docs.astral.sh/uv/getting-started/installation/)
on macOS, Linux, or WSL:

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Restart your shell if `uv` is not found. In your project directory, run:

```sh
uv init --bare --python 3.13
uv add uptimely-core
```

Run the CLI with `uv run uptimely <command>`. Install any project code
dependencies needed by the workflow into this environment.
