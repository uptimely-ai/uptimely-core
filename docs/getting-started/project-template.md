## Project template

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
source init.sh
```

### Dev Container

Alternatively, the environment can be established to an isolated Dev Container. Install Docker and the VS Code Dev Containers extension, then open the example folder in VS Code and
select **Dev Containers: Reopen in Container** from the Command Palette.

The container runs the same setup script automatically. Run the
commands below in its terminal. Explorer port 8001 is forwarded to your host.

## Verify setup

Depending on setup, use either of:

* `uptimely build`
* `uv run uptimely build`
