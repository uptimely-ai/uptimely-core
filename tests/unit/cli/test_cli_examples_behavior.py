import argparse
import io
import pathlib
import sys
import tomllib
import zipfile
from email import message

import pytest

from uptimely.cli import cli, examples


def _archive(files: dict[str, str]) -> bytes:
    """Create an in-memory repository archive."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture()
def github(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace metadata and HTTP access with a public repository fixture."""
    package_metadata = message.Message()
    package_metadata["Project-URL"] = "Documentation, https://example.com/docs"
    package_metadata["Project-URL"] = "Repository, https://github.com/example/project"
    monkeypatch.setattr(examples.metadata, "metadata", lambda name: package_metadata)
    monkeypatch.setattr(examples.metadata, "version", lambda name: "1.2.3")
    urls: list[str] = []
    archive = _archive(
        {
            "project-main/readme.md": "not an example",
            "project-main/example/README.md": "Example guide",
            "project-main/example/init.sh": "setup",
            "project-main/example/run.py": "print('example')",
            "project-main/example/data/sample.csv": "x\n1\n",
            "project-main/src/module.py": "not an example",
            "project-main/explorer/example/guide.md": "not a root-level example",
            "project-main/tests/examples/fixture.py": "not a root-level example",
            "project-main/example/empty/": "",
        }
    )

    def open_url(url: str, *, timeout: int) -> io.BytesIO:
        assert timeout > 0
        urls.append(url)
        return io.BytesIO(archive)

    monkeypatch.setattr(examples.request, "urlopen", open_url)
    return urls


def test_cli_success(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["uptimely", "example"])
    cli.main()
    assert github == ["https://codeload.github.com/example/project/zip/v1.2.3"]
    assert f"Downloaded examples to {tmp_path / 'example'}" in capsys.readouterr().out
    assert (tmp_path / "example/README.md").exists()


def test_cli_output_and_revision(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "demo" / "example"
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "example", "--output", str(output), "--ref", "v1.0"],
    )
    cli.main()
    assert github == ["https://codeload.github.com/example/project/zip/v1.0"]
    assert (output / "README.md").exists()


def test_examples_without_subcommand_downloads_default_destination(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    calls: list[tuple[pathlib.Path, str | None, bool]] = []
    monkeypatch.setattr(
        examples,
        "download_examples",
        lambda output, ref, *, no_setup: calls.append((output, ref, no_setup)) or output,
    )
    monkeypatch.setattr(sys, "argv", ["uptimely", "example"])

    cli.main()

    assert calls == [(pathlib.Path("example"), None, False)]
    assert "Downloaded examples to example" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("arguments", "expected_output", "expected_ref", "expected_no_setup"),
    [
        (["example", "--output", "samples", "--ref", "HEAD"], "samples", "HEAD", False),
        (["example", "--dir", "pump-analytics", "--ref", "HEAD"], "pump-analytics", "HEAD", False),
        (["example", "--no-setup", "--dir", "pump-analytics"], "pump-analytics", None, True),
    ],
)
def test_examples_options_work_with_command(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    expected_output: str,
    expected_ref: str | None,
    expected_no_setup: bool,
) -> None:
    calls: list[tuple[pathlib.Path, str | None, bool]] = []
    monkeypatch.setattr(
        examples,
        "download_examples",
        lambda output, ref, *, no_setup: calls.append((output, ref, no_setup)) or output,
    )
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])

    cli.main()

    assert calls == [(pathlib.Path(expected_output), expected_ref, expected_no_setup)]


def test_download_help_describes_version_default(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "example", "--help"])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 0
    help_text = " ".join(capsys.readouterr().out.split())
    assert "installed package version" in help_text
    assert "default branch" not in help_text


def test_write_failure_cleans_staging(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open = pathlib.Path.open

    def open_path(path: pathlib.Path, mode: str = "r", *args: object, **kwargs: object) -> object:
        if mode == "xb":
            raise PermissionError("Cannot write examples")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(pathlib.Path, "open", open_path)
    with pytest.raises(PermissionError, match="Cannot write"):
        examples.download_examples(tmp_path / "example")
    assert list(tmp_path.iterdir()) == []


def test_destination_created_during_download_is_preserved(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "example"
    open_url = examples.request.urlopen

    def download(url: str, *, timeout: int) -> object:
        output.mkdir()
        (output / "keep.txt").write_text("keep")
        return open_url(url, timeout=timeout)

    monkeypatch.setattr(examples.request, "urlopen", download)
    with pytest.raises(FileExistsError, match="already exists"):
        examples.download_examples(output)
    assert (output / "keep.txt").read_text() == "keep"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("arguments", [[], ["example", "unknown"], ["examples"]])
def test_cli_requires_valid_subcommands(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_console_script_registration() -> None:
    root = pathlib.Path(__file__).parents[3]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert config["project"]["scripts"]["uptimely"] == "uptimely.cli.cli:main"
    assert config["project"]["scripts"]["uptimely-mcp"] == "uptimely.mcp.server:main"


@pytest.mark.parametrize(
    ("arguments", "command", "expected_options"),
    [
        (
            ["build", "project", "--features", "feature", "--log-level", "debug"],
            "build",
            {
                "project_root_argument": pathlib.Path("project"),
                "features": ["feature"],
                "log_level": "debug",
            },
        ),
        (
            ["run", "project", "--preview", "3"],
            "run",
            {"project_root_argument": pathlib.Path("project"), "preview": 3, "build": False},
        ),
        (
            ["run", "project", "--build"],
            "run",
            {"project_root_argument": pathlib.Path("project"), "build": True},
        ),
        (
            ["explore", "project", "--host", "0.0.0.0", "--port", "0"],
            "explore",
            {"project_root_argument": pathlib.Path("project"), "host": "0.0.0.0", "port": 0},
        ),
        (
            ["build", "project"],
            "build",
            {"project_root_argument": pathlib.Path("project")},
        ),
        (
            ["run", "project"],
            "run",
            {"project_root_argument": pathlib.Path("project"), "build": False},
        ),
        (
            ["run", "project", "--build"],
            "run",
            {"project_root_argument": pathlib.Path("project"), "build": True},
        ),
        (
            ["explore", "project"],
            "explore",
            {"project_root_argument": pathlib.Path("project")},
        ),
        (
            ["feature-graph", "project"],
            "feature-graph",
            {"project_root_argument": pathlib.Path("project")},
        ),
        (
            ["export", "project", "--output", "site"],
            "export",
            {"project_root_argument": pathlib.Path("project")},
        ),
    ],
)
def test_top_level_commands_use_existing_handlers_and_options(
    monkeypatch: pytest.MonkeyPatch,
    arguments: list[str],
    command: str,
    expected_options: dict[str, object],
) -> None:
    handlers = {
        "build": cli.project,
        "run": cli.engine,
        "explore": cli.explorer,
        "feature-graph": cli.spec,
        "export": cli.explorer,
    }
    captured: list[argparse.Namespace] = []
    monkeypatch.setattr(handlers[command], "run", lambda args, _parser: captured.append(args))
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])

    cli.main()

    assert len(captured) == 1
    assert {key: getattr(captured[0], key) for key in expected_options} == expected_options


@pytest.mark.parametrize(
    "arguments",
    [
        ["build", "project", "--project-root", "other"],
        ["run", "project", "--project-root", "other"],
        ["explore", "project", "--project-root", "other"],
    ],
)
def test_project_root_cannot_be_both_positional_and_an_option(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    arguments: list[str],
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "project root may be provided positionally or with --project-root, not both" in (
        capsys.readouterr().err
    )
