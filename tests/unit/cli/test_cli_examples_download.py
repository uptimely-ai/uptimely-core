import io
import os
import pathlib
import stat
import subprocess
import sys
import zipfile
from email import message
from importlib import metadata
from urllib import error as urllib_error

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


def test_download_examples(tmp_path: pathlib.Path, github: list[str]) -> None:
    output = tmp_path / "nested" / "example"
    assert examples.download_examples(output) == output
    assert github == ["https://codeload.github.com/example/project/zip/v1.2.3"]
    assert sorted(
        str(path.relative_to(output)) for path in output.rglob("*") if path.is_file()
    ) == [
        "README.md",
        "data/sample.csv",
        "init.sh",
        "run.py",
    ]
    assert (output / "run.py").read_text() == "print('example')"
    assert not (output / "empty").exists()
    assert list(output.parent.iterdir()) == [output]


def test_download_revision(tmp_path: pathlib.Path, github: list[str]) -> None:
    examples.download_examples(tmp_path / "example", "feature/demo")
    assert github == ["https://codeload.github.com/example/project/zip/feature%2Fdemo"]


@pytest.mark.parametrize("version", ["0.1.0", "0.2.3", "0.2.0.dev4", "0.2.0rc1"])
def test_download_matches_installed_version(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    version: str,
) -> None:
    monkeypatch.setattr(examples.metadata, "version", lambda name: version)
    examples.download_examples(tmp_path / "example")
    assert github == [f"https://codeload.github.com/example/project/zip/v{version}"]


def test_explicit_revision_does_not_require_version(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def missing_version(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(examples.metadata, "version", missing_version)
    examples.download_examples(tmp_path / "example", "HEAD")
    assert github == ["https://codeload.github.com/example/project/zip/HEAD"]


def test_missing_version_is_reported(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def missing_version(name: str) -> str:
        raise metadata.PackageNotFoundError(name)

    monkeypatch.setattr(examples.metadata, "version", missing_version)
    monkeypatch.setattr(sys, "argv", ["uptimely", "example", "--output", str(tmp_path / "example")])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 1
    assert "ERROR    |" in capsys.readouterr().err
    assert github == []
    assert list(tmp_path.iterdir()) == []


def test_missing_release_tag_does_not_fall_back(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def missing_tag(url: str, *, timeout: int) -> io.BytesIO:
        github.append(url)
        raise urllib_error.HTTPError(url, 404, "Not found", {}, None)

    monkeypatch.setattr(examples.request, "urlopen", missing_tag)
    monkeypatch.setattr(sys, "argv", ["uptimely", "example", "--output", str(tmp_path / "example")])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 1
    error = capsys.readouterr().err
    assert "v1.2.3" in error
    assert "--ref" in error
    assert github == ["https://codeload.github.com/example/project/zip/v1.2.3"]
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("source_path", ["samples", "demos/examples"])
def test_configured_examples_source(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    source_path: str,
) -> None:
    data = _archive(
        {
            f"project-main/{source_path}/run.py": "configured example",
            "project-main/example/ignored.py": "not the configured source",
        }
    )
    monkeypatch.setattr(examples, "EXAMPLES_FOLDER", source_path)
    monkeypatch.setattr(examples.request, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    output = tmp_path / "example"
    examples.download_examples(output)
    assert (output / "run.py").read_text() == "configured example"
    assert list(output.iterdir()) == [output / "run.py"]


@pytest.mark.parametrize("kind", ["directory", "file", "symlink"])
def test_existing_destination_is_preserved(
    tmp_path: pathlib.Path, github: list[str], kind: str
) -> None:
    output = tmp_path / "example"
    if kind == "directory":
        output.mkdir()
        (output / "keep.txt").write_text("keep")
    elif kind == "file":
        output.write_text("keep")
    else:
        output.symlink_to(tmp_path / "missing")
    with pytest.raises(FileExistsError, match="already exists"):
        examples.download_examples(output)
    assert github == []
    if kind == "directory":
        assert (output / "keep.txt").read_text() == "keep"
    elif kind == "file":
        assert output.read_text() == "keep"
    else:
        assert output.is_symlink()


def test_no_setup_merges_into_existing_directory(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    data = _archive(
        {
            "project/example/README.md": "guide",
            "project/example/pyproject.toml": "setup",
            "project/example/init.sh": "example setup",
            "project/example/.devcontainer/devcontainer.json": "{}",
            "project/example/__init__.py": "",
            "project/example/src/analytics.py": "code",
            "project/example/src/init.sh": "nested script",
            "project/example/spec/spec.py": "spec",
            "project/example/uptimely.toml": "",
            "project/example/data/input/sample.csv": "data",
        }
    )
    monkeypatch.setattr(examples.request, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    (tmp_path / "README.md").write_text("existing guide")
    (tmp_path / "init.sh").write_text("existing script")
    (tmp_path / ".devcontainer").mkdir()
    (tmp_path / ".devcontainer/devcontainer.json").write_text("existing container")
    (tmp_path / "src").mkdir()
    (tmp_path / "src/other.py").write_text("existing code")
    monkeypatch.setattr(sys, "argv", ["uptimely", "example", "--no-setup", "--dir", str(tmp_path)])

    cli.main()

    assert (tmp_path / "pyproject.toml").read_text() == "setup"
    assert (tmp_path / "README.md").read_text() == "existing guide"
    assert (tmp_path / "init.sh").read_text() == "existing script"
    assert (tmp_path / ".devcontainer/devcontainer.json").read_text() == "existing container"
    assert (tmp_path / "src/other.py").read_text() == "existing code"
    for path in (
        "__init__.py",
        "src/analytics.py",
        "src/init.sh",
        "spec/spec.py",
        "uptimely.toml",
        "data/input/sample.csv",
    ):
        assert (tmp_path / path).is_file()


def test_no_setup_excludes_init_script_from_new_directory(
    tmp_path: pathlib.Path, github: list[str]
) -> None:
    output = tmp_path / "example"
    examples.download_examples(output, no_setup=True)
    assert not (output / "init.sh").exists()
    assert (output / "run.py").is_file()


@pytest.mark.parametrize("kind", ["file", "directory", "symlink", "parent-symlink"])
def test_no_setup_rejects_conflicts_before_copying(
    tmp_path: pathlib.Path, github: list[str], kind: str
) -> None:
    output = tmp_path / "example"
    output.mkdir()
    if kind == "parent-symlink":
        outside = tmp_path / "outside"
        outside.mkdir()
        (output / "data").symlink_to(outside, target_is_directory=True)
    else:
        target = output / "run.py"
        if kind == "file":
            target.write_text("existing")
        elif kind == "directory":
            target.mkdir()
        else:
            target.symlink_to(tmp_path / "missing")

    with pytest.raises(FileExistsError):
        examples.download_examples(output, no_setup=True)

    assert not (output / "README.md").exists()
    if kind == "parent-symlink":
        assert not list(outside.iterdir())
        assert not (output / "run.py").exists()
    elif kind == "file":
        assert target.read_text() == "existing"
        assert not (output / "data/sample.csv").exists()


def test_no_setup_example_builds_and_runs_in_existing_environment(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    source = pathlib.Path(__file__).resolve().parents[3] / "example"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for directory in ("src", "spec", "data/input"):
            for path in (source / directory).rglob("*"):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, f"project/example/{path.relative_to(source)}")
        archive.write(source / "uptimely.toml", "project/example/uptimely.toml")
        archive.write(source / "pyproject.toml", "project/example/pyproject.toml")
    monkeypatch.setattr(
        examples.request, "urlopen", lambda *args, **kwargs: io.BytesIO(buffer.getvalue())
    )
    output = tmp_path / "pump-analytics"
    examples.download_examples(output, no_setup=True)
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    for command in ("build", "run"):
        if command == "run":
            renamed = tmp_path / "renamed-example"
            output.rename(renamed)
            output = renamed
        subprocess.run(
            [
                sys.executable,
                "-c",
                "from uptimely.cli import cli; cli.main()",
                command,
                str(output),
            ],
            cwd=tmp_path,
            env=environment,
            check=True,
            capture_output=True,
            text=True,
            timeout=90,
        )
    assert (output / "pyproject.toml").is_file()


def test_examples_cli_reports_existing_default_destination(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "example"
    output.mkdir()
    (output / "keep.txt").write_text("keep")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["uptimely", "example"])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    message = capsys.readouterr().err
    assert f"Examples destination already exists: {output}" in message
    assert "Nothing was overwritten." in message
    assert "--dir DIR" in message
    assert (output / "keep.txt").read_text() == "keep"


@pytest.mark.parametrize(
    "path",
    [
        "project/example/../../escape.txt",
        "project/example/../escape.txt",
        "project/example/nested/../../../escape.txt",
        "project/example/C:\\escape.txt",
        "/example/escape.txt",
        "project/example//escape.txt",
    ],
)
def test_unsafe_paths_leave_no_output(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    data = _archive({"project/example/ok.txt": "ok", path: "unsafe"})
    monkeypatch.setattr(examples.request, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    with pytest.raises(ValueError, match="Unsafe"):
        examples.download_examples(tmp_path / "example")
    assert list(tmp_path.iterdir()) == []


def test_symlinks_are_rejected(
    tmp_path: pathlib.Path, github: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        link = zipfile.ZipInfo("project/example/link")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        archive.writestr(link, "../../escape")
    monkeypatch.setattr(
        examples.request,
        "urlopen",
        lambda *args, **kwargs: io.BytesIO(buffer.getvalue()),
    )
    with pytest.raises(ValueError, match="Unsupported"):
        examples.download_examples(tmp_path / "example")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "data",
    [b"not a zip", _archive({"project/readme.md": "no examples"})],
    ids=["invalid-zip", "missing-examples"],
)
def test_invalid_archives_are_reported(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    data: bytes,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(examples.request, "urlopen", lambda *args, **kwargs: io.BytesIO(data))
    monkeypatch.setattr(sys, "argv", ["uptimely", "example", "--output", str(tmp_path / "example")])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "ERROR    |" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "error",
    [
        urllib_error.URLError("offline"),
        urllib_error.HTTPError("https://example.com", 404, "Not found", {}, None),
    ],
)
def test_network_errors_are_reported(
    tmp_path: pathlib.Path,
    github: list[str],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    error: urllib_error.URLError,
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(examples.request, "urlopen", fail)
    monkeypatch.setattr(sys, "argv", ["uptimely", "example", "--output", str(tmp_path / "example")])
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 1
    assert "ERROR    |" in capsys.readouterr().err
    assert list(tmp_path.iterdir()) == []


def test_missing_repository_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(examples.metadata, "metadata", lambda name: message.Message())
    with pytest.raises(ValueError, match="no Repository URL"):
        examples._repository_url()


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
        examples._archive_url(url, "HEAD")


def test_git_suffix_and_empty_revision() -> None:
    assert examples._archive_url("https://github.com/example/project.git/", "v1.0") == (
        "https://codeload.github.com/example/project/zip/v1.0"
    )
    with pytest.raises(ValueError, match="must not be empty"):
        examples._archive_url("https://github.com/example/project", "")
