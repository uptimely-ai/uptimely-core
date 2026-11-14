"""Tests for the example project setup script."""

import os
import pathlib
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("installation", ["existing", "curl"])
@pytest.mark.parametrize("sourced", [False, True])
def test_init_installs_uv_when_needed_and_syncs_project(
    tmp_path: pathlib.Path, installation: str, sourced: bool
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    home = tmp_path / "home"
    user_bin = home / ".local" / "bin"
    user_bin.mkdir(parents=True)
    for command in ("dirname", "sh"):
        executable = shutil.which(command)
        assert executable is not None
        (bin_dir / command).symlink_to(executable)

    uv_template = tmp_path / "uv"
    uv_template.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$TEST_LOG"\n')
    uv_template.chmod(0o755)
    if installation == "existing":
        shutil.copy(uv_template, user_bin / "uv")
    else:
        curl = bin_dir / "curl"
        curl.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' '#!/bin/sh' '/bin/cp \"$TEST_UV_TEMPLATE\" \"$HOME/.local/bin/uv\"'\n"
        )
        curl.chmod(0o755)

    script = pathlib.Path(__file__).resolve().parents[2] / "example" / "init.sh"
    log = tmp_path / "uv-args"
    args = ["bash", str(script)]
    if sourced:
        args = [
            "bash",
            "-c",
            'before="$(set +o)"; source "$1" || exit $?; '
            '[[ "$before" == "$(set +o)" ]] && command -v uv',
            "bash",
            str(script),
        ]
    result = subprocess.run(
        args,
        cwd=tmp_path,
        env={
            **os.environ,
            "HOME": str(home),
            "PATH": str(bin_dir),
            "TEST_LOG": str(log),
            "TEST_UV_TEMPLATE": str(uv_template),
        },
        capture_output=True,
        text=True,
        check=False,
        executable=shutil.which("bash"),
    )

    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ["sync", "--project", str(script.parent)]


@pytest.mark.parametrize(("curl_available", "exit_code"), [(True, 22), (False, 127)])
@pytest.mark.parametrize("sourced", [False, True])
def test_init_stops_when_uv_download_fails(
    tmp_path: pathlib.Path, curl_available: bool, exit_code: int, sourced: bool
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for command in ("dirname", "sh"):
        executable = shutil.which(command)
        assert executable is not None
        (bin_dir / command).symlink_to(executable)
    if curl_available:
        curl = bin_dir / "curl"
        curl.write_text("#!/bin/sh\nexit 22\n")
        curl.chmod(0o755)

    script = pathlib.Path(__file__).resolve().parents[2] / "example" / "init.sh"
    args = ["bash", str(script)]
    if sourced:
        args = [
            "bash",
            "-c",
            'source "$1"; status=$?; echo continued; exit "$status"',
            "bash",
            str(script),
        ]
    result = subprocess.run(
        args,
        cwd=tmp_path,
        env={**os.environ, "HOME": str(tmp_path), "PATH": str(bin_dir)},
        capture_output=True,
        text=True,
        check=False,
        executable=shutil.which("bash"),
    )

    assert result.returncode == exit_code
    if sourced:
        assert "continued" in result.stdout
