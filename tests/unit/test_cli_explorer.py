"""Tests for serving the analytics explorer from the command line."""

import pathlib
import shlex
import sys

import jinja2
import pytest

from uptimely import compiler, spec
from uptimely.cli import cli, explorer

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]
SPEC_PATH = REPOSITORY_ROOT / "examples/pump_analytics/_generated/spec/spec.json"


@pytest.fixture
def saved_plan(tmp_path: pathlib.Path) -> pathlib.Path:
    target = tmp_path / "saved_plan.json"
    compiled = compiler.Compiler(spec.load_spec(SPEC_PATH)).compile()
    compiled.callables[0].arguments["saved_plan_marker"] = "CLI-saved-plan-marker"
    compiled.export_json(target)
    return target


@pytest.mark.parametrize(
    "arguments",
    [
        ["explorer"],
        ["explorer", "unknown"],
        ["explorer", "build"],
        ["explorer", "build", "--unknown"],
        ["explorer", "generate", "--spec", str(SPEC_PATH)],
        ["docs"],
    ],
)
def test_explorer_requires_valid_arguments(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 2


@pytest.mark.parametrize("missing", ["spec", "plan", "both"])
@pytest.mark.parametrize("custom_inputs", [False, True])
@pytest.mark.parametrize("root_option", ["cwd", "relative", "absolute"])
def test_explorer_reports_missing_inputs_before_loading(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    missing: str,
    custom_inputs: bool,
    root_option: str,
) -> None:
    project_root = tmp_path / "project with spaces"
    project_root.mkdir()
    (project_root / "_generated").mkdir()
    monkeypatch.chdir(project_root if root_option == "cwd" else tmp_path)
    arguments = ["uptimely", "explorer", "serve"]
    if root_option != "cwd":
        root = project_root.name if root_option == "relative" else str(project_root)
        arguments.extend(["--project-root", root])
    spec_path = project_root / "_generated/spec/spec.json"
    plan_path = project_root / "_generated/compile/execution_plan.json"
    if custom_inputs:
        spec_path = pathlib.Path("custom spec.json")
        plan_path = pathlib.Path("custom plan.json")
        arguments.extend(["--spec", str(spec_path), "--plan", str(plan_path)])
    if missing == "plan":
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text("must not be loaded", encoding="utf-8")
    elif missing == "spec":
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text("must not be loaded", encoding="utf-8")

    def unexpected_call(*args: object, **kwargs: object) -> None:
        pytest.fail("Missing inputs must be reported before loading or serving")

    monkeypatch.setattr(explorer.common, "load_spec", unexpected_call)
    monkeypatch.setattr(explorer, "serve_explorer", unexpected_call)
    monkeypatch.setattr(sys, "argv", arguments)

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    result = capsys.readouterr()
    assert not result.out
    assert "uptimely: error: Missing Explorer input files:" in result.err
    if missing in ("spec", "both"):
        assert f"Spec JSON: {spec_path.resolve()}" in result.err
    else:
        assert "Spec JSON:" not in result.err
    if missing in ("plan", "both"):
        assert f"Execution plan JSON: {plan_path.resolve()}" in result.err
    else:
        assert "Execution plan JSON:" not in result.err
    command = shlex.join(["uptimely", "project", "build", "--project-root", str(project_root)])
    assert command in result.err
    assert "--spec" in result.err
    assert "--plan" in result.err
    assert "Traceback" not in result.err
    assert not (project_root / "_generated/explorer").exists()
    assert not (pathlib.Path.cwd() / "_generated/explorer").exists()


@pytest.mark.parametrize(
    "failure",
    [
        PermissionError("Cannot write website"),
        ValueError("Invalid spec"),
        ModuleNotFoundError("Missing function module"),
        AttributeError("Missing function"),
        TypeError("Invalid callable signature"),
        jinja2.TemplateError("Invalid HTML template"),
    ],
)
def test_explorer_build_errors_are_reported(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    failure: Exception,
    saved_plan: pathlib.Path,
) -> None:
    class BrokenExplorer:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def create_html(self, *args: object, **kwargs: object) -> pathlib.Path:
            raise failure

    monkeypatch.setattr(explorer.explorer_module, "Explorer", BrokenExplorer)
    monkeypatch.setattr(explorer, "serve_explorer", lambda *args: None)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "serve",
            "--spec",
            str(SPEC_PATH),
            "--plan",
            str(saved_plan),
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    result = capsys.readouterr()
    assert not result.out
    assert f"uptimely: error: {failure}" in result.err


@pytest.mark.parametrize("content", [None, "not JSON", '{"version": "unsupported"}'])
def test_explorer_rejects_missing_or_invalid_spec(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
    saved_plan: pathlib.Path,
) -> None:
    spec_definition = tmp_path / "spec.json"
    if content is not None:
        spec_definition.write_text(content, encoding="utf-8")
    output = tmp_path / "site"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "serve",
            "--spec",
            str(spec_definition),
            "--plan",
            str(saved_plan),
            "--directory",
            str(output),
        ],
    )

    with pytest.raises(SystemExit) as error:
        cli.main()

    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
    assert not output.exists()


@pytest.mark.parametrize("explicit_plan", [False, True])
def test_explorer_uses_saved_plan_without_compiling(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    saved_plan: pathlib.Path,
    explicit_plan: bool,
) -> None:
    def fail_compile(*args: object, **kwargs: object) -> None:
        pytest.fail("Explorer must not recompile a saved plan")

    monkeypatch.setattr(compiler.Compiler, "compile", fail_compile)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(explorer, "serve_explorer", lambda *args: None)
    if explicit_plan:
        arguments = ["--plan", saved_plan.name]
    else:
        default_plan = tmp_path / "_generated/compile/execution_plan.json"
        default_plan.parent.mkdir(parents=True)
        default_plan.write_bytes(saved_plan.read_bytes())
        arguments = []
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "serve",
            "--spec",
            str(SPEC_PATH),
            *arguments,
        ],
    )

    cli.main()

    graph = tmp_path / "_generated/explorer/plan/graph.html"
    assert "CLI-saved-plan-marker" in graph.read_text(encoding="utf-8")


@pytest.mark.parametrize("content", [None, "not JSON", '{"plan_version": "unsupported"}'])
def test_explorer_rejects_missing_or_invalid_plan(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    content: str | None,
) -> None:
    saved_plan = tmp_path / "plan.json"
    if content is not None:
        saved_plan.write_text(content, encoding="utf-8")
    output = tmp_path / "website"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "uptimely",
            "explorer",
            "serve",
            "--spec",
            str(SPEC_PATH),
            "--plan",
            str(saved_plan),
            "--directory",
            str(output),
        ],
    )
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 1
    assert "uptimely: error:" in capsys.readouterr().err
    assert not output.exists()
