"""Tests for the analytics command-line interface."""

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

from uptimely import analytics
from uptimely.cli import analytics as analytics_cli
from uptimely.cli import cli

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
PUMP_MODULE = "examples.pump_analytics.config.analytics.analytics"
PUMP_ENTRYPOINT = f"{PUMP_MODULE}:python_analytics"


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "analytics", "build", *arguments])
    cli.main()


@pytest.mark.parametrize(
    ("module", "name", "entities"),
    [
        (PUMP_MODULE, "Pump analytics", {"pump", "pump_telemetry"}),
        (
            "examples.simple_analytics.config.analytics.analytics",
            "Simple analytics",
            {"simple_analytics"},
        ),
    ],
)
def test_build_example_in_fresh_process(
    tmp_path: pathlib.Path, module: str, name: str, entities: set[str]
) -> None:
    output = tmp_path / "export/analytics.json"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "uptimely.cli.cli",
            "analytics",
            "build",
            "--entrypoint",
            f"{module}:python_analytics",
            "--project-root",
            str(REPOSITORY_ROOT),
            "--output",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert f"Analytics written to {output}" in result.stdout
    assert not result.stderr
    analytics_definition = analytics.load_analytics(output)
    assert analytics_definition.name == name
    assert set(analytics_definition.entities) == entities
    assert analytics_definition.source.name == "python_api"
    assert analytics_definition.source.generated is True
    assert analytics_definition.functions.by_operation("read")


@pytest.mark.parametrize("explicit_root", [False, True])
def test_build_default_output_and_import_root(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    explicit_root: bool,
) -> None:
    module = f"export_default_{explicit_root}"
    (tmp_path / f"{module}.py").write_text(
        "from examples.simple_analytics.config.analytics.analytics import python_analytics\n",
        encoding="utf-8",
    )
    arguments = ["--entrypoint", f"{module}:python_analytics"]
    if explicit_root:
        arguments.extend(["--project-root", str(tmp_path)])
    else:
        monkeypatch.chdir(tmp_path)
    invoke(monkeypatch, *arguments)
    output = tmp_path / "_generated/analytics/analytics.json"
    assert json.loads(output.read_text(encoding="utf-8"))["name"] == "Simple analytics"
    assert "Analytics written to" in capsys.readouterr().out


def test_build_explicit_output_is_relative_to_working_directory(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    invoke(
        monkeypatch,
        "--entrypoint",
        PUMP_ENTRYPOINT,
        "--project-root",
        str(REPOSITORY_ROOT),
        "--output",
        "custom/analytics.json",
    )
    assert (tmp_path / "custom/analytics.json").is_file()


@pytest.mark.parametrize(
    ("module", "content", "error_text"),
    [
        ("missing_export_module", None, "No module named"),
        ("missing_export_declaration", "", "python_analytics"),
        (
            "invalid_export_declaration",
            "python_analytics = {}",
            "must be a PythonAnalytics",
        ),
        (
            "broken_export_dependency",
            "import missing_export_dependency",
            "missing_export_dependency",
        ),
        (
            "invalid_export_analytics",
            "from uptimely.analytics import python as python_analytics\n"
            "python_analytics = python_analytics.PythonAnalytics()",
            "At least one entity is required",
        ),
    ],
)
def test_build_errors_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    module: str,
    content: str | None,
    error_text: str,
) -> None:
    if content is not None:
        (tmp_path / f"{module}.py").write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "--entrypoint",
            f"{module}:python_analytics",
            "--project-root",
            str(tmp_path),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert error_text in result.err
    assert not result.out
    assert not (tmp_path / "_generated/analytics/analytics.json").exists()


def test_build_write_errors_are_reported(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "blocked"
    output.write_text("not a directory", encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "--entrypoint",
            PUMP_ENTRYPOINT,
            "--output",
            str(output / "analytics.json"),
        )
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "uptimely: error:" in result.err
    assert not result.out


def test_build_reports_missing_sources(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)
    assert error.value.code == 1
    result = capsys.readouterr()
    assert "No analytics source found" in result.err
    assert "config/analytics/analytics.py" in result.err
    assert "config/analytics/analytics.json" in result.err
    assert not result.out
    assert not (tmp_path / "_generated").exists()


@pytest.mark.parametrize("example", ["pump_analytics", "simple_analytics"])
@pytest.mark.parametrize("explicit_root", [False, True])
def test_build_discovers_example_in_fresh_process(
    tmp_path: pathlib.Path, example: str, explicit_root: bool
) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    shutil.copyfile(REPOSITORY_ROOT / "examples/__init__.py", examples / "__init__.py")
    project_root = examples / example
    shutil.copytree(
        REPOSITORY_ROOT / "examples" / example,
        project_root,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    arguments = ["--project-root", str(project_root)] if explicit_root else []
    cwd = tmp_path if explicit_root else project_root
    result = subprocess.run(
        [sys.executable, "-m", "uptimely.cli.cli", "analytics", "build", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stderr
    output = project_root / "_generated/analytics/analytics.json"
    assert json.loads(output.read_text(encoding="utf-8"))["entities"]
    assert not result.stderr
    plan = subprocess.run(
        [sys.executable, "-m", "uptimely.cli.cli", "plan", "build", *arguments],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert plan.returncode == 0, plan.stderr
    assert (project_root / "_generated/compile/execution_plan.json").is_file()


def test_build_discovers_unpackaged_project(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "config/analytics/analytics.py"
    source.parent.mkdir(parents=True)
    source.write_text(
        "from uptimely.analytics import python as api\n"
        "from uptimely.analytics.python import entity\n"
        "from . import metadata\n"
        "python_analytics = api.PythonAnalytics("
        "entities=[entity.Entity(id='example', name='Example', dimensions=[], datasets=[])], "
        "name=metadata.NAME)\n",
        encoding="utf-8",
    )
    (source.parent / "metadata.py").write_text("NAME = 'Local project'\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, "-m", "uptimely.cli.cli", "analytics", "build"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr
    output = tmp_path / "_generated/analytics/analytics.json"
    assert json.loads(output.read_text(encoding="utf-8"))["name"] == "Local project"


@pytest.mark.parametrize("explicit_source", [False, True])
def test_build_json_source(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, explicit_source: bool
) -> None:
    root = tmp_path / "project"
    source = root / "config/analytics/analytics.json"
    source.parent.mkdir(parents=True)
    shutil.copyfile(
        REPOSITORY_ROOT / "examples/pump_analytics/_generated/analytics/analytics.json",
        source,
    )
    arguments = ["--project-root", str(root)]
    if explicit_source:
        (source.parent / "analytics.py").write_text(
            "raise RuntimeError('Explicit JSON must bypass discovery')\n", encoding="utf-8"
        )
        monkeypatch.chdir(tmp_path)
        arguments.extend(
            ["--analytics", "project/config/analytics/analytics.json", "--output", "out.json"]
        )
    invoke(monkeypatch, *arguments)

    output = (
        tmp_path / "out.json" if explicit_source else root / "_generated/analytics/analytics.json"
    )
    assert analytics.load_analytics(output) == analytics.load_analytics(source)


def test_build_rejects_ambiguous_sources(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = tmp_path / "config/analytics"
    source.mkdir(parents=True)
    (source / "analytics.py").write_text(
        "raise RuntimeError('Must not import ambiguous source')\n", encoding="utf-8"
    )
    (source / "analytics.json").write_text("not JSON", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path))

    assert error.value.code == 1
    assert "Ambiguous analytics sources" in capsys.readouterr().err
    assert not (tmp_path / "_generated").exists()

    invoke(monkeypatch, "--project-root", str(tmp_path), "--entrypoint", PUMP_ENTRYPOINT)
    assert (tmp_path / "_generated/analytics/analytics.json").is_file()


@pytest.mark.parametrize("content", [None, "not JSON", '{"version": "unsupported"}'])
def test_build_invalid_json_source(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
) -> None:
    source = tmp_path / "analytics.json"
    if content is not None:
        source.write_text(content, encoding="utf-8")
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path), "--analytics", str(source))
    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
    assert not (tmp_path / "_generated").exists()


def test_build_rejects_multiple_explicit_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--entrypoint", PUMP_ENTRYPOINT, "--analytics", "analytics.json")
    assert error.value.code == 2


def test_build_operation_rejects_multiple_sources(tmp_path: pathlib.Path) -> None:
    with pytest.raises(ValueError, match="either a Python entrypoint or an analytics JSON"):
        analytics_cli.build_analytics(
            PUMP_ENTRYPOINT,
            tmp_path / "output.json",
            tmp_path,
            source=tmp_path / "input.json",
        )
    assert not (tmp_path / "output.json").exists()


def test_build_selects_named_attribute(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "custom_declaration.py").write_text(
        "from examples.simple_analytics.config.analytics.analytics "
        "import python_analytics as definition\n"
        "python_analytics = None\n",
        encoding="utf-8",
    )
    invoke(
        monkeypatch,
        "--entrypoint",
        "custom_declaration:definition",
        "--project-root",
        str(tmp_path),
    )
    output = tmp_path / "_generated/analytics/analytics.json"
    assert analytics.load_analytics(output).name == "Simple analytics"


@pytest.mark.parametrize(
    "entrypoint",
    ["", "module", ":definition", "module:", "module:one:two", "bad/module:definition"],
)
def test_build_rejects_invalid_entrypoint(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    entrypoint: str,
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--entrypoint", entrypoint, "--project-root", str(tmp_path))
    assert error.value.code == 1
    assert "Expected 'module:attribute'" in capsys.readouterr().err
    assert not (tmp_path / "_generated").exists()


@pytest.mark.parametrize(
    ("attribute", "error_text"),
    [("missing", "missing"), ("factory", "must be a PythonAnalytics")],
)
def test_build_reports_invalid_selected_attribute(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    attribute: str,
    error_text: str,
) -> None:
    (tmp_path / "invalid_attributes.py").write_text(
        "def factory():\n    raise RuntimeError('Factories must not be called')\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit) as error:
        invoke(
            monkeypatch,
            "--entrypoint",
            f"invalid_attributes:{attribute}",
            "--project-root",
            str(tmp_path),
        )
    assert error.value.code == 1
    assert error_text in capsys.readouterr().err
    assert not (tmp_path / "_generated").exists()


def test_build_rejects_old_module_option(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--module", PUMP_MODULE)
    assert error.value.code == 2
    assert "unrecognized arguments: --module" in capsys.readouterr().err


def test_build_reports_invalid_discovered_python(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "invalid_python_project"
    source = root / "config/analytics/analytics.py"
    source.parent.mkdir(parents=True)
    (root / "__init__.py").write_text("", encoding="utf-8")
    source.write_text("def invalid(:\n", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(root))

    assert error.value.code == 1
    assert "uptimely: error: invalid syntax" in capsys.readouterr().err
    assert not (root / "_generated").exists()


def test_export_action_is_rejected(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(
        sys, "argv", ["uptimely", "analytics", "export", "--entrypoint", PUMP_ENTRYPOINT]
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2
    assert "invalid choice: 'export'" in capsys.readouterr().err


def test_analytics_help_lists_build(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "analytics", "--help"])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 0
    result = capsys.readouterr()
    assert "{build,feature-graph}" in result.out
    assert "export" not in result.out
    assert not result.err
