"""Tests for the installed command and GitHub example downloads."""

import io
import stat
import sys
import tomllib
from email.message import Message
from pathlib import Path
from urllib.error import HTTPError, URLError
from zipfile import ZipFile, ZipInfo

import pytest

from uptimely.cli import cli


def _archive(files: dict[str, str]) -> bytes:
    """Create an in-memory repository archive."""
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return buffer.getvalue()


@pytest.fixture()
def github(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace metadata and HTTP access with a public repository fixture."""
    package_metadata = Message()
    package_metadata["Project-URL"] = "Documentation, https://example.com/docs"
    package_metadata["Project-URL"] = "Repository, https://github.com/example/project"
    monkeypatch.setattr(cli, "metadata", lambda name: package_metadata)
    urls: list[str] = []
    archive = _archive(
        {
            "project-main/readme.md": "not an example",
            "project-main/examples/README.md": "Example guide",
            "project-main/examples/example_1/run.py": "print('example')",
            "project-main/examples/example_1/data/sample.csv": "x\n1\n",
            "project-main/src/module.py": "not an example",
            "project-main/docs/examples/guide.md": "not a root-level example",
            "project-main/tests/examples/fixture.py": "not a root-level example",
            "project-main/examples/empty/": "",
        }
    )

    def open_url(url: str, *, timeout: int) -> io.BytesIO:
        assert timeout > 0
        urls.append(url)
        return io.BytesIO(archive)

    monkeypatch.setattr(cli, "urlopen", open_url)
    return urls


def test_download_examples(tmp_path: Path, github: list[str]) -> None:
    output = tmp_path / "nested" / "examples"
    assert cli.download_examples(output) == output
    assert github == ["https://codeload.github.com/example/project/zip/HEAD"]
    assert sorted(
        str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()
    ) == [
        "README.md",
        "example_1/data/sample.csv",
        "example_1/run.py",
    ]
    assert (output / "example_1/run.py").read_text() == "print('example')"
    assert not (output / "empty").exists()
    assert list(output.parent.iterdir()) == [output]


def test_download_revision(tmp_path: Path, github: list[str]) -> None:
    cli.download_examples(tmp_path / "examples", "feature/demo")
    assert github == ["https://codeload.github.com/example/project/zip/feature%2Fdemo"]


@pytest.mark.parametrize("source_path", ["samples", "demos/examples"])
def test_configured_examples_source(
    tmp_path: Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    source_path: str,
) -> None:
    data = _archive(
        {
            f"project-main/{source_path}/run.py": "configured example",
            "project-main/examples/ignored.py": "not the configured source",
        }
    )
    monkeypatch.setattr(cli, "EXAMPLES_FOLDER", source_path)
    monkeypatch.setattr(cli, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    output = tmp_path / "examples"
    cli.download_examples(output)
    assert (output / "run.py").read_text() == "configured example"
    assert list(output.iterdir()) == [output / "run.py"]


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_existing_destination_is_preserved(tmp_path: Path, github: list[str], kind: str) -> None:
    output = tmp_path / "examples"
    if kind == "directory":
        output.mkdir()
        (output / "keep.txt").write_text("keep")
    elif kind == "file":
        output.write_text("keep")
    else:
        output.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError, match="already exists"):
        cli.download_examples(output)
    assert github == []
    if kind == "directory":
        assert (output / "keep.txt").read_text() == "keep"
    elif kind == "file":
        assert output.read_text() == "keep"
    else:
        assert output.is_symlink()


@pytest.mark.parametrize(
    "path",
    [
        "project/examples/../../escape.txt",
        "project/examples/../escape.txt",
        "project/examples/nested/../../../escape.txt",
        "project/examples/C:\\escape.txt",
        "/examples/escape.txt",
        "project/examples//escape.txt",
    ],
)
def test_unsafe_paths_leave_no_output(
    tmp_path: Path, github: list[str], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    data = _archive({"project/examples/ok.txt": "ok", path: "unsafe"})
    monkeypatch.setattr(cli, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    with pytest.raises(ValueError, match="Unsafe"):
        cli.download_examples(tmp_path / "examples")
    assert list(tmp_path.iterdir()) == []


def test_symlinks_are_rejected(
    tmp_path: Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w") as archive:
        link = ZipInfo("project/examples/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "../../escape")
    monkeypatch.setattr(cli, "urlopen", lambda *args, **kwargs: io.BytesIO(buffer.getvalue()))
    with pytest.raises(ValueError, match="Unsupported"):
        cli.download_examples(tmp_path / "examples")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("data", [b"not a zip", _archive({"project/readme.md": "no examples"})])
def test_invalid_archives_are_reported(
    tmp_path: Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(cli, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    monkeypatch.setattr(
        sys, "argv", ["uptimely", "examples", "download", "--output", str(tmp_path / "examples")]
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "error", [URLError("offline"), HTTPError("https://example.com", 404, "Not found", {}, None)]
)
def test_network_errors_are_reported(
    tmp_path: Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: URLError,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(cli, "urlopen", fail)
    monkeypatch.setattr(
        sys, "argv", ["uptimely", "examples", "download", "--output", str(tmp_path / "examples")]
    )
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_missing_repository_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "metadata", lambda name: Message())
    with pytest.raises(ValueError, match="no Repository URL"):
        cli._repository_url()


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/example/project",
        "https://example.com/example/project",
        "https://github.com/example/project/extra",
        "https://github.com/example/project?query=1",
        "https://user@github.com/example/project",
    ],
)
def test_invalid_repository_urls(url: str) -> None:
    with pytest.raises(ValueError, match="public HTTPS GitHub"):
        cli._archive_url(url, "HEAD")


def test_git_suffix_and_empty_revision() -> None:
    assert cli._archive_url("https://github.com/example/project.git/", "v1.0") == (
        "https://codeload.github.com/example/project/zip/v1.0"
    )
    with pytest.raises(ValueError, match="must not be empty"):
        cli._archive_url("https://github.com/example/project", "")


def test_cli_success(
    tmp_path: Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["uptimely", "examples", "download"])
    cli.main()
    assert f"Downloaded examples to {tmp_path / 'examples'}" in capsys.readouterr().out
    assert (tmp_path / "examples/README.md").exists()


def test_cli_output_and_revision(
    tmp_path: Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "demo" / "examples"
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "examples", "download", "--output", str(output), "--ref", "v1.0"],
    )
    cli.main()
    assert github == ["https://codeload.github.com/example/project/zip/v1.0"]
    assert (output / "README.md").exists()


def test_write_failure_cleans_staging(
    tmp_path: Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_open = Path.open

    def open_path(path: Path, mode: str = "r", *args: object, **kwargs: object) -> object:
        if mode == "xb":
            raise PermissionError("Cannot write examples")
        return original_open(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_path)
    with pytest.raises(PermissionError, match="Cannot write"):
        cli.download_examples(tmp_path / "examples")
    assert list(tmp_path.iterdir()) == []


def test_destination_created_during_download_is_preserved(
    tmp_path: Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "examples"
    open_url = cli.urlopen

    def download(url: str, *, timeout: int) -> object:
        output.mkdir()
        (output / "keep.txt").write_text("keep")
        return open_url(url, timeout=timeout)

    monkeypatch.setattr(cli, "urlopen", download)
    with pytest.raises(FileExistsError, match="already exists"):
        cli.download_examples(output)
    assert (output / "keep.txt").read_text() == "keep"
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize("arguments", [[], ["examples"], ["examples", "unknown"]])
def test_cli_requires_valid_subcommands(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2


def test_console_script_registration() -> None:
    root = Path(__file__).parents[2]
    config = tomllib.loads((root / "pyproject.toml").read_text())
    assert config["project"]["scripts"]["uptimely"] == "uptimely.cli.cli:main"
    assert config["project"]["scripts"]["uptimely-mcp"] == "uptimely.mcp.server:main"
