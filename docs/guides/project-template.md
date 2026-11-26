# Project template

Fetch the full project template from the latest stable release.
Its setup script uses curl to install uv if needed and syncs the dependencies.

From outside an existing example project, run the following in Bash. On Debian
or Ubuntu, install `curl` and `unzip` if needed:

```sh
sudo apt install curl unzip
curl -fLO https://uptimely.ai/core/example.zip
unzip example.zip -d pump-analytics
cd pump-analytics
```

## Development environment

### Local setup

Inititalize the project with uv:

```sh
source code/init.sh
```

### Dev Container

Alternatively, the environment can be established to an isolated Dev Container. Install Docker and the VS Code Dev Containers extension, then open the `code/` folder in VS Code and
select **Dev Containers: Reopen in Container** from the Command Palette.

The container runs the same setup script automatically. Run the
commands below in its terminal. Explorer port 8001 is forwarded to your host.

## Verify setup

Run commands from the example project root. In the Dev Container, its virtual
environment is already on `PATH`:

```sh
uptimely build
uptimely run
```

For local setup, select the environment synced from `code/pyproject.toml`:

```sh
uv run --project code uptimely build
uv run --project code uptimely run
```
