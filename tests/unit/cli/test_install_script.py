import os
import pathlib
import shutil
import subprocess

import pytest
from ruamel import yaml

SCRIPT = pathlib.Path(__file__).resolve().parents[3] / "scripts" / "install.sh"
RELEASE_WORKFLOW = SCRIPT.parents[1] / ".github" / "workflows" / "release.yml"


def _write_executable(path: pathlib.Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o755)


def test_installs_user_tool_without_modifying_project(tmp_path: pathlib.Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    binaries = tmp_path / "bin"
    binaries.mkdir()
    tool_bin = tmp_path / "tool-bin"
    tool_bin.mkdir()
    log = tmp_path / "uv.log"
    _write_executable(tool_bin / "uptimely", "#!/bin/sh\nexit 0\n")
    _write_executable(
        binaries / "uv",
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$UV_TEST_LOG"\n'
        'if [ "$*" = "tool dir --bin" ]; then printf "%s\\n" "$UV_TEST_BIN"; fi\n',
    )
    env = os.environ | {
        "HOME": str(home),
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "UV_TEST_BIN": str(tool_bin),
        "UV_TEST_LOG": str(log),
    }

    result = subprocess.run(
        ["sh", str(SCRIPT)], cwd=tmp_path, env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding="utf-8").splitlines() == [
        "tool install --python 3.13 uptimely-core@latest",
        "tool dir --bin",
        "tool update-shell",
    ]
    assert not (tmp_path / "pyproject.toml").exists()
    assert not (tmp_path / ".venv").exists()
    assert "Restart your terminal" in result.stdout


def test_reports_installation_failure(tmp_path: pathlib.Path) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    _write_executable(binaries / "uv", "#!/bin/sh\nprintf '%s\\n' 'install failed' >&2\nexit 1\n")
    env = os.environ | {"HOME": str(tmp_path), "PATH": f"{binaries}:{os.environ['PATH']}"}

    result = subprocess.run(
        ["sh", str(SCRIPT)], cwd=tmp_path, env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode != 0
    assert "install failed" in result.stderr
    assert "Uptimely is installed" not in result.stdout


def test_reports_missing_executable(tmp_path: pathlib.Path) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    _write_executable(
        binaries / "uv",
        '#!/bin/sh\nif [ "$*" = "tool dir --bin" ]; then printf "%s\\n" "$HOME"; fi\n',
    )
    env = os.environ | {"HOME": str(tmp_path), "PATH": f"{binaries}:{os.environ['PATH']}"}

    result = subprocess.run(
        ["sh", str(SCRIPT)], cwd=tmp_path, env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode != 0
    assert "Uptimely was not found" in result.stderr


def test_shell_setup_sees_original_path(tmp_path: pathlib.Path) -> None:
    local_bin = tmp_path / ".local" / "bin"
    local_bin.mkdir(parents=True)
    log = tmp_path / "path.log"
    _write_executable(local_bin / "uptimely", "#!/bin/sh\nexit 0\n")
    _write_executable(
        local_bin / "uv",
        "#!/bin/sh\n"
        'if [ "$*" = "tool dir --bin" ]; then printf "%s\\n" "$HOME/.local/bin"; fi\n'
        'if [ "$*" = "tool update-shell" ]; then printf "%s\\n" "$PATH" > "$UV_TEST_LOG"; fi\n',
    )
    env = os.environ | {"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "UV_TEST_LOG": str(log)}

    result = subprocess.run(
        ["sh", str(SCRIPT)], cwd=tmp_path, env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding="utf-8").strip() == "/usr/bin:/bin"


def test_shell_setup_failure_reports_recovery(tmp_path: pathlib.Path) -> None:
    binaries = tmp_path / "bin"
    binaries.mkdir()
    _write_executable(tmp_path / "uptimely", "#!/bin/sh\nexit 0\n")
    _write_executable(
        binaries / "uv",
        "#!/bin/sh\n"
        'if [ "$*" = "tool dir --bin" ]; then printf "%s\\n" "$HOME"; fi\n'
        'if [ "$*" = "tool update-shell" ]; then exit 1; fi\n',
    )
    env = os.environ | {"HOME": str(tmp_path), "PATH": f"{binaries}:{os.environ['PATH']}"}

    result = subprocess.run(
        ["sh", str(SCRIPT)], cwd=tmp_path, env=env, text=True, capture_output=True, check=False
    )

    assert result.returncode != 0
    assert "automatic PATH setup did not complete" in result.stderr
    assert f"add {tmp_path} to your shell PATH" in result.stderr


@pytest.mark.parametrize("version", ["0.13.0", "0.13.0.dev1"])
def test_release_installer_installs_matching_version(tmp_path: pathlib.Path, version: str) -> None:
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copyfile(SCRIPT, scripts / "install.sh")
    (tmp_path / "dist").mkdir()
    workflow = yaml.YAML(typ="safe").load(RELEASE_WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["release"]["steps"]
    step = next(item for item in steps if item.get("name") == "Create versioned installer")
    env = os.environ | {"GITHUB_REF_NAME": f"v{version}"}

    subprocess.run(["bash", "-e", "-c", step["run"]], cwd=tmp_path, env=env, check=True)

    binaries = tmp_path / "bin"
    binaries.mkdir()
    log = tmp_path / "uv.log"
    _write_executable(tmp_path / "uptimely", "#!/bin/sh\nexit 0\n")
    _write_executable(
        binaries / "uv",
        "#!/bin/sh\n"
        'printf "%s\\n" "$*" >> "$UV_TEST_LOG"\n'
        'if [ "$*" = "tool dir --bin" ]; then printf "%s\\n" "$HOME"; fi\n',
    )
    env = env | {
        "HOME": str(tmp_path),
        "PATH": f"{binaries}:{os.environ['PATH']}",
        "UV_TEST_LOG": str(log),
    }

    result = subprocess.run(
        ["sh", str(tmp_path / "dist" / "install.sh")],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text(encoding="utf-8").splitlines()[0] == (
        f"tool install --python 3.13 uptimely-core=={version}"
    )
