"""Tests for building generated project resources without executing spec."""

import json
import pathlib
import shutil
import subprocess
import sys

import pytest

from uptimely import project, spec
from uptimely.cli import cli, plan
from uptimely.cli import spec as spec_cli
from uptimely.compiler import plan as plan_module

REPOSITORY_ROOT = pathlib.Path(__file__).parents[2]


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "project", "build", *arguments])
    cli.main()


@pytest.mark.parametrize("example", ["pump_analytics", "simple_analytics"])
@pytest.mark.parametrize("explicit_root", [False, True])
@pytest.mark.parametrize("empty_generated", [False, True])
def test_project_build_examples(
    tmp_path: pathlib.Path, example: str, explicit_root: bool, empty_generated: bool
) -> None:
    examples = tmp_path / "examples"
    examples.mkdir()
    shutil.copyfile(REPOSITORY_ROOT / "examples/__init__.py", examples / "__init__.py")
    root = examples / example
    shutil.copytree(
        REPOSITORY_ROOT / "examples" / example,
        root,
        ignore=shutil.ignore_patterns("_generated", "__pycache__"),
    )
    if empty_generated:
        (root / project.GENERATED_DIR).mkdir()
    arguments = ["--project-root", str(root)] if explicit_root else []
    command = [sys.executable, "-m", "uptimely.cli.cli", "project", "build", *arguments]
    cwd = tmp_path if explicit_root else root
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)

    assert result.returncode == 0, result.stderr
    assert not result.stderr
    assert "Spec written to" in result.stdout
    assert "Execution plan:" in result.stdout
    spec_path = root / project.SPEC_JSON_FILE
    plan_path = root / project.EXECUTION_PLAN_FILE
    assert spec.load_spec(spec_path).entities
    original_plan = plan_module.ExecutionPlan.from_json(plan_path)
    assert original_plan.callables
    original_spec = spec_path.read_bytes()
    spec_path.write_text("outdated", encoding="utf-8")
    plan_path.write_text("outdated", encoding="utf-8")

    rebuilt = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=60)

    assert rebuilt.returncode == 0, rebuilt.stderr
    assert spec_path.read_bytes() == original_spec
    rebuilt_plan = plan_module.ExecutionPlan.from_json(plan_path)
    assert {item.id: item for item in rebuilt_plan.callables} == {
        item.id: item for item in original_plan.callables
    }
    assert len(rebuilt_plan.execution_stages) == len(original_plan.execution_stages)


@pytest.mark.parametrize("source_kind", ["entrypoint", "json"])
def test_project_build_explicit_source_does_not_execute_workflow(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, source_kind: str
) -> None:
    monkeypatch.chdir(tmp_path)
    root = tmp_path / "project"
    root.mkdir()
    (root / "build_functions.py").write_text(
        "import polars\n"
        "def read() -> polars.DataFrame:\n"
        "    raise RuntimeError('Build must not execute spec')\n",
        encoding="utf-8",
    )
    source = tmp_path / "source.json"
    source.write_text(
        json.dumps(
            {
                "version": "0.2.0",
                "name": "Build-only test",
                "functions": {
                    "read": {
                        "operation": "read",
                        "entrypoint": "build_functions:read",
                        "returns": "dataframe",
                    }
                },
                "entities": {
                    "example": {
                        "name": "Example",
                        "datasets": [
                            {
                                "id": "values",
                                "features": {"value": {}},
                                "mappings": {
                                    "read": {
                                        "binding": {"function": "read"},
                                        "features": {"outputs": ["$features.value"]},
                                    }
                                },
                            }
                        ],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    if source_kind == "entrypoint":
        (root / "declaration.py").write_text(
            "from uptimely.spec import python as api\n"
            "from uptimely.spec.python import bind, dataset, entity, feature, mapping, ref\n"
            "import build_functions\n"
            "definition = api.PythonSpec(entities=[entity.Entity(\n"
            "    id='example', name='Example', dimensions=[], datasets=[dataset.Dataset(\n"
            "        id='values', features=[feature.Feature(id='value')], mappings=[\n"
            "            mapping.Mapping(id='read', bind=bind.bind(ref.function(\n"
            "                build_functions.read, operation='read')), "
            "outputs=[ref.feature('value')])])])])\n",
            encoding="utf-8",
        )
        arguments = ["--entrypoint", "declaration:definition"]
    else:
        arguments = ["--spec", "source.json"]

    invoke(monkeypatch, "--project-root", str(root), *arguments)

    assert spec.load_spec(root / project.SPEC_JSON_FILE).entities
    assert plan_module.ExecutionPlan.from_json(root / project.EXECUTION_PLAN_FILE).callables
    assert not (root / project.EXPLORER_OUTPUT_DIR).exists()


@pytest.mark.parametrize("stage", ["spec", "compile", "write"])
@pytest.mark.parametrize(
    "failure",
    [
        OSError("Cannot access artifact"),
        ValueError("Invalid document"),
        ImportError("Missing dependency"),
        AttributeError("Missing attribute"),
        TypeError("Invalid declaration"),
        SyntaxError("Invalid Python"),
    ],
)
def test_project_build_reports_stage_failures(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    stage: str,
    failure: Exception,
) -> None:
    calls: list[str] = []

    def fail(*args: object, **kwargs: object) -> None:
        calls.append(stage)
        raise failure

    if stage == "spec":
        monkeypatch.setattr(spec_cli, "build_spec", fail)
        monkeypatch.setattr(
            plan, "compile_plan", lambda *args: pytest.fail("Must stop after spec failure")
        )
    else:
        source = REPOSITORY_ROOT / "examples/pump_analytics/_generated/spec/spec.json"
        (tmp_path / project.SPEC_SOURCE_DIR).mkdir(parents=True)
        shutil.copyfile(source, tmp_path / project.SPEC_JSON_ENTRY_FILE)
        if stage == "compile":
            monkeypatch.setattr(plan, "compile_plan", fail)
        else:
            monkeypatch.setattr(plan_module.ExecutionPlan, "export_json", fail)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path))

    assert error.value.code == 1
    assert calls == [stage]
    result = capsys.readouterr()
    expected = "Spec" if stage == "spec" else "Execution plan"
    assert f"uptimely: error: {expected} build failed: {failure}" in result.err
    assert "Execution plan:" not in result.out
    assert not (tmp_path / project.EXECUTION_PLAN_FILE).exists()


def test_project_build_missing_source(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path))
    assert error.value.code == 1
    assert "Spec build failed: No spec source found" in capsys.readouterr().err
    assert not (tmp_path / project.GENERATED_DIR).exists()


def test_project_build_preserves_previous_plan_on_compile_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    source = REPOSITORY_ROOT / "examples/pump_analytics/_generated/spec/spec.json"
    (tmp_path / project.SPEC_SOURCE_DIR).mkdir(parents=True)
    shutil.copyfile(source, tmp_path / project.SPEC_JSON_ENTRY_FILE)
    saved_plan = tmp_path / project.EXECUTION_PLAN_FILE
    saved_plan.parent.mkdir(parents=True)
    saved_plan.write_text("previous plan", encoding="utf-8")

    def fail(*args: object, **kwargs: object) -> None:
        raise ValueError("Invalid function signature")

    monkeypatch.setattr(plan, "compile_plan", fail)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(tmp_path))

    assert error.value.code == 1
    assert "Execution plan build failed" in capsys.readouterr().err
    assert spec.load_spec(tmp_path / project.SPEC_JSON_FILE).entities
    assert saved_plan.read_text(encoding="utf-8") == "previous plan"


def test_project_build_help(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "project", "build", "--help"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 0
    result = capsys.readouterr()
    assert "--entrypoint MODULE:ATTRIBUTE" in result.out
    assert "--spec" in result.out
    assert "--project-root" in result.out
    assert not result.err


@pytest.mark.parametrize(
    "arguments",
    [
        ["project"],
        ["project", "unknown"],
        ["project", "build", "--entrypoint", "module:attribute", "--spec", "source.json"],
        ["project", "build", "--output", "custom"],
    ],
)
def test_project_requires_valid_arguments(
    monkeypatch: pytest.MonkeyPatch, arguments: list[str]
) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", *arguments])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
