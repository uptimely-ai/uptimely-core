"""Check repository MCP setup without installing packages or running analytics."""

import json
import os
import pathlib
import shutil
import subprocess

import pytest

REPOSITORY_ROOT = pathlib.Path(__file__).parents[3]
INSTALL_SCRIPT = REPOSITORY_ROOT / "scripts" / "install-mcp.sh"
BASH_PATH = shutil.which("bash")
BASH = BASH_PATH or "bash"

pytestmark = pytest.mark.skipif(BASH_PATH is None, reason="Repository setup script requires Bash")


def test_installer_uses_existing_poetry_environment(tmp_path: pathlib.Path) -> None:
    """Installation and building run in the checkout without changing Poetry settings."""
    executable = tmp_path / "poetry"
    log = tmp_path / "commands"
    executable.write_text(
        '#!/bin/bash\nprintf "%s|%s\\n" "$PWD" "$*" >> "$MCP_SETUP_LOG"\n',
        encoding="utf-8",
    )
    executable.chmod(0o755)
    environment = {
        **os.environ,
        "PATH": os.pathsep.join([str(tmp_path), os.defpath]),
        "MCP_SETUP_LOG": str(log),
    }

    result = subprocess.run(
        [BASH, str(INSTALL_SCRIPT)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        f"{REPOSITORY_ROOT}|install --extras mcp",
        f"{REPOSITORY_ROOT}|run uptimely build example",
    ]
    assert "MCP: List Servers" in result.stdout
    assert "No background server is needed" in result.stdout


def test_installer_help_needs_no_poetry(tmp_path: pathlib.Path) -> None:
    """Help is available before any setup or dependency checks."""
    result = subprocess.run(
        [BASH, str(INSTALL_SCRIPT), "--help"],
        env={**os.environ, "PATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "does not start a server" in result.stdout


def test_installer_reports_missing_poetry(tmp_path: pathlib.Path) -> None:
    """A missing setup dependency produces actionable instructions."""
    result = subprocess.run(
        [BASH, str(INSTALL_SCRIPT)],
        env={**os.environ, "PATH": str(tmp_path)},
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert "Poetry is required" in result.stderr
    assert "uptimely-core[mcp]" in result.stderr


def test_installer_rejects_unexpected_arguments() -> None:
    """Mistyped options do not proceed with installation."""
    result = subprocess.run(
        [BASH, str(INSTALL_SCRIPT), "--unknown"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert "--help" in result.stderr


def test_vscode_mcp_uses_poetry_without_environment_path_assumptions() -> None:
    """The workspace launcher works with local and externally located Poetry environments."""
    configuration = json.loads((REPOSITORY_ROOT / ".vscode" / "mcp.json").read_text())

    assert configuration["servers"]["uptimely"] == {
        "type": "stdio",
        "command": "poetry",
        "cwd": "${workspaceFolder}",
        "args": [
            "run",
            "uptimely-mcp",
            "--project-root",
            "${workspaceFolder}/example",
        ],
    }
