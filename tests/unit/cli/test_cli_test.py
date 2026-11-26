import json
import os
import pathlib
import re
import sys

import polars as pl
import pytest
from support import examples as example_support

from uptimely import application, plan
from uptimely.cli import cli, test_display
from uptimely.codebase.python import entrypoint
from uptimely.test import models, runner


def invoke(monkeypatch: pytest.MonkeyPatch, *arguments: str) -> None:
    monkeypatch.setattr(sys, "argv", ["uptimely", "test", *arguments])
    cli.main()


def test_default_folder_requires_saved_build(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    project = tmp_path / "project"
    (project / "tests" / "uptimely").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project))

    assert error.value.code == 1
    assert "build" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("create_file", [False, True])
def test_missing_default_folder_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    create_file: bool,
) -> None:
    monkeypatch.chdir(tmp_path)
    if create_file:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "uptimely").write_text("", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch)

    assert error.value.code == 1
    assert "Configured test folder tests/uptimely not found" in capsys.readouterr().err


@pytest.mark.parametrize("absolute", [False, True])
def test_configured_folder_is_used(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    absolute: bool,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    folder = project / "custom-tests"
    path = str(folder) if absolute else "custom-tests"
    (project / "uptimely.toml").write_text(f'[test]\npath = "{path}"\n', encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(project))
    assert error.value.code == 1
    assert f"Configured test folder {path} not found" in capsys.readouterr().err

    folder.mkdir()
    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--project-root", str(project))
    assert error.value.code == 1
    assert "build" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("config_arg", ["prod", "override.toml"])
def test_selected_config_is_used(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    config_arg: str,
) -> None:
    (tmp_path / "uptimely.toml").write_text('[test]\npath = "default"\n', encoding="utf-8")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "prod.toml").write_text('[test]\npath = "selected"\n', encoding="utf-8")
    (tmp_path / "override.toml").write_text('[test]\npath = "selected"\n', encoding="utf-8")
    (tmp_path / "selected").mkdir()
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, "--config", config_arg)

    assert error.value.code == 1
    assert "build" in capsys.readouterr().err.lower()


@pytest.mark.parametrize("path", ['""', "42"])
def test_invalid_test_path_is_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    path: str,
) -> None:
    (tmp_path / "uptimely.toml").write_text(f"[test]\npath = {path}\n", encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(tmp_path))

    assert error.value.code == 1
    assert "test.path" in capsys.readouterr().err


def _case_project(
    tmp_path: pathlib.Path, factory: example_support.ProjectFactory
) -> tuple[pathlib.Path, pathlib.Path, dict]:
    project = factory(tmp_path / "project")
    folder = project / "cases"
    folder.mkdir()
    case_path = folder / "pump_series.json"
    suite = json.loads(
        (project / "tests" / "uptimely" / "pump_series.json").read_text(encoding="utf-8")
    )
    case_path.write_text(json.dumps(suite), encoding="utf-8")
    (project / "case-config.toml").write_text(
        '[code]\nsrc = "code/src"\n[test]\npath = "cases"\n', encoding="utf-8"
    )
    return project, case_path, suite


def test_test_command_uses_saved_source_and_preserves_run(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    (project / "code" / "src" / "pump_analytics.py").write_text(
        'raise RuntimeError("live source must not be used")\n', encoding="utf-8"
    )
    test_data = project / "artifacts" / "test" / "data"
    test_data.mkdir(parents=True)
    (test_data / "stale.json").write_text("{}", encoding="utf-8")
    case_artifacts = project / "artifacts" / "test" / "cases"
    case_artifacts.mkdir()
    (case_artifacts / "stale.json").write_text("{}", encoding="utf-8")
    run_path = project / "artifacts" / "run"
    run_path.mkdir(parents=True, exist_ok=True)
    sentinel = run_path / "sentinel"
    sentinel.write_text("unchanged", encoding="utf-8")

    invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    saved_cases = json.loads((case_artifacts / case_path.name).read_text(encoding="utf-8"))
    operator = next(iter(suite))
    saved_case = saved_cases[operator]["cases"]["basic"]
    assert report["status"] == "passed"
    assert report["build"]["fingerprint"]
    assert len(report["cases"]) == 1
    assert set(report["cases"][0]) == {"profile", "operator", "case", "status", "message"}
    assert saved_case["inputs"] == suite[operator]["cases"]["basic"]["inputs"]
    assert saved_case["expected"] == suite[operator]["cases"]["basic"]["expected"]
    assert saved_case["actual"] == saved_case["expected"]["return"]
    call = saved_case["call"]
    assert call == {
        "function": "pump_analytics:aggregate",
        "arguments": {
            "dataset": "$dataset",
            "aggregations": {"bearing_temperature": "max"},
            "dimensions": ["machine_series_id"],
            "rename": {"bearing_temperature": "bearing_temperature_series_max"},
        },
        "dataframe_inputs": {"/dataset": "dataset"},
    }
    assert not test_data.exists()
    assert not (case_artifacts / "stale.json").exists()
    output = capsys.readouterr().out
    assert "1 passed, 0 failed" in output
    assert "Inputs:" not in output
    assert sentinel.read_text(encoding="utf-8") == "unchanged"


def test_test_command_builds_before_running_cases(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    source = project / "code" / "src" / "pump_analytics.py"
    original = "getattr(pl.col(feature), method)().alias(rename.get(feature, feature))"
    changed = "(getattr(pl.col(feature), method)() + 1.0).alias(rename.get(feature, feature))"
    content = source.read_text(encoding="utf-8")
    assert original in content
    source.write_text(content.replace(original, changed), encoding="utf-8")
    case = next(iter(suite.values()))["cases"]["basic"]
    case["expected"]["return"][0]["bearing_temperature_series_max"] = 71.0
    case_path.write_text(json.dumps(suite), encoding="utf-8")

    invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"), "--build")

    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    assert report["status"] == "passed"
    assert len(report["cases"]) == 1


def test_legacy_data_is_preserved_when_configured_as_source(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, _ = _case_project(tmp_path, example_project_factory)
    source = project / "artifacts" / "test" / "data"
    source.mkdir(parents=True)
    source_case = source / case_path.name
    source_case.write_bytes(case_path.read_bytes())
    config = project / "case-config.toml"
    config.write_text('[test]\npath = "artifacts/test/data"\n', encoding="utf-8")

    invoke(monkeypatch, str(project), "--config", str(config))

    assert source_case.read_bytes() == case_path.read_bytes()
    assert (project / "artifacts" / "test" / "cases" / case_path.name).is_file()


def test_case_artifact_folder_cannot_be_used_as_source(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, _ = _case_project(tmp_path, example_project_factory)
    source = project / "artifacts" / "test" / "cases"
    source.mkdir(parents=True)
    source_case = source / case_path.name
    source_case.write_bytes(case_path.read_bytes())
    config = project / "case-config.toml"
    config.write_text('[test]\npath = "artifacts/test/cases"\n', encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project), "--config", str(config))

    assert error.value.code == 1
    assert source_case.read_bytes() == case_path.read_bytes()


def test_test_command_does_not_run_after_build_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    report = tmp_path / "artifacts" / "test" / "test.json"
    report.parent.mkdir(parents=True)
    report.write_text("previous report", encoding="utf-8")

    def fail_build(self: application.Uptimely) -> application.BuildBundle:
        raise application.ProjectBuildError("generation", "invalid source")

    monkeypatch.setattr(application.Uptimely, "build", fail_build)
    monkeypatch.setattr(
        runner.TestRunner,
        "run",
        lambda *_args, **_kwargs: pytest.fail("Tests must not run after a failed build"),
    )

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(tmp_path), "--build")

    assert error.value.code == 1
    assert "Project build generation failed: invalid source" in capsys.readouterr().err
    assert report.read_text(encoding="utf-8") == "previous report"


def test_test_command_saves_failures_and_continues(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    cases = next(iter(suite.values()))["cases"]
    cases["other"] = json.loads(json.dumps(cases["basic"]))
    cases["basic"]["expected"]["return"][0]["bearing_temperature_series_max"] = 1.0
    case_path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    assert error.value.code == 1
    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    assert report["status"] == "failed"
    assert [case["status"] for case in report["cases"]] == ["failed", "passed"]
    saved = json.loads(
        (project / "artifacts" / "test" / "cases" / case_path.name).read_text(encoding="utf-8")
    )
    assert all(case["call"] is not None for case in next(iter(saved.values()))["cases"].values())
    assert "does not match expected" in capsys.readouterr().out


@pytest.mark.parametrize("fail", [False, True])
def test_case_saves_resolved_arguments_before_call(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, fail: bool
) -> None:
    (tmp_path / "uptimely.toml").write_text("[params]\nlimit = 7\n", encoding="utf-8")
    invocation = plan.Invocation(
        id="calculate",
        entrypoint="test:calculate",
        arguments={
            "dataset": "$datasets.pump.read",
            "options": {
                "limit": "$params.limit",
                "a/b~c": ["$datasets.pump.read", None],
                "literal": {"$case_input": "dataset"},
                "literal_marker": "$dataset",
            },
        },
        returns=None,
    )
    case = models.Case.model_validate(
        {"inputs": {"dataset": [{"x": 1}]}, "expected": {"return": [{"x": 1}]}}
    )
    calls = []

    def calculate(dataset: pl.LazyFrame, options: dict) -> pl.LazyFrame:
        calls.append(options["limit"])
        assert options["a/b~c"][0] is dataset
        options["limit"] = 99
        if fail:
            raise RuntimeError("function failed")
        return dataset

    monkeypatch.setattr(entrypoint.Entrypoint, "load", lambda self: calculate)
    test_runner = runner.TestRunner(application.Uptimely(tmp_path))

    result, _ = test_runner._run_case(
        "pump",
        "calculate",
        "basic",
        invocation,
        case,
        {"test:calculate": entrypoint.Entrypoint("test:calculate")},
    )

    assert calls == [7]
    assert result.status == ("error" if fail else "passed")
    assert result.call is not None
    assert result.call.model_dump() == {
        "function": "test:calculate",
        "arguments": {
            "dataset": "$dataset",
            "options": {
                "limit": 7,
                "a/b~c": ["$dataset", None],
                "literal": {"$case_input": "dataset"},
                "literal_marker": "$dataset",
            },
        },
        "dataframe_inputs": {"/dataset": "dataset", "/options/a~1b~0c/0": "dataset"},
    }


def test_unresolved_arguments_do_not_record_or_execute_call(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invocation = plan.Invocation(
        id="calculate",
        entrypoint="test:calculate",
        arguments={"dataset": "$datasets.pump.read", "limit": "$params.missing"},
        returns=None,
    )
    case = models.Case.model_validate(
        {"inputs": {"dataset": [{"x": 1}]}, "expected": {"return": [{"x": 1}]}}
    )
    monkeypatch.setattr(entrypoint.Entrypoint, "load", lambda self: pytest.fail("Must not execute"))
    result, _ = runner.TestRunner(application.Uptimely(tmp_path))._run_case(
        "pump",
        "calculate",
        "basic",
        invocation,
        case,
        {"test:calculate": entrypoint.Entrypoint("test:calculate")},
    )

    assert result.status == "error"
    assert "Unresolved parameter: missing" in result.message
    assert result.call is None


def test_case_call_marks_each_dataframe_with_its_argument_name(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    invocation = plan.Invocation(
        id="calculate",
        entrypoint="test:calculate",
        arguments={"left": "$datasets.a.read", "right": "$datasets.b.read"},
        returns=None,
    )
    case = models.Case.model_validate(
        {
            "inputs": {"left": [{"x": 1}], "right": [{"x": 2}]},
            "expected": {"return": [{"x": 1}, {"x": 2}]},
        }
    )

    def calculate(left: pl.LazyFrame, right: pl.LazyFrame) -> pl.LazyFrame:
        return pl.concat([left, right])

    monkeypatch.setattr(entrypoint.Entrypoint, "load", lambda self: calculate)
    result, _ = runner.TestRunner(application.Uptimely(tmp_path))._run_case(
        "p",
        "calculate",
        "basic",
        invocation,
        case,
        {"test:calculate": entrypoint.Entrypoint("test:calculate")},
    )

    assert result.status == "passed"
    assert result.call is not None
    assert result.call.arguments == {"left": "$left", "right": "$right"}
    assert result.call.dataframe_inputs == {"/left": "left", "/right": "right"}


@pytest.mark.parametrize("value", [object(), float("nan")])
def test_unserializable_arguments_report_case_error_without_execution(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, value: object
) -> None:
    app = application.Uptimely(tmp_path)
    app.config.params.root["limit"] = value
    invocation = plan.Invocation(
        id="calculate",
        entrypoint="test:calculate",
        arguments={"dataset": "$datasets.pump.read", "limit": "$params.limit"},
        returns=None,
    )
    case = models.Case.model_validate(
        {"inputs": {"dataset": [{"x": 1}]}, "expected": {"return": [{"x": 1}]}}
    )
    monkeypatch.setattr(entrypoint.Entrypoint, "load", lambda self: pytest.fail("Must not execute"))

    result, _ = runner.TestRunner(app)._run_case(
        "pump",
        "calculate",
        "basic",
        invocation,
        case,
        {"test:calculate": entrypoint.Entrypoint("test:calculate")},
    )

    assert result.status == "error"
    assert result.message
    assert result.call is None


def test_test_command_saves_actual_rows_when_empty_output_was_expected(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    next(iter(suite.values()))["cases"]["basic"]["expected"]["return"] = []
    case_path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(SystemExit):
        invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    saved = json.loads(
        (project / "artifacts" / "test" / "cases" / case_path.name).read_text(encoding="utf-8")
    )
    assert next(iter(saved.values()))["cases"]["basic"]["actual"] == [
        {"machine_series_id": "S1", "bearing_temperature_series_max": 70.0}
    ]


@pytest.mark.parametrize("mismatch", [False, True])
def test_show_prints_all_case_inputs_and_expected_outputs(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
    mismatch: bool,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    operator, definition = next(iter(suite.items()))
    case = definition["cases"]["basic"]
    case["inputs"]["dataset"] = [
        {"machine_series_id": "S1", "bearing_temperature": float(value)} for value in range(60, 67)
    ]
    case["expected"]["return"][0]["bearing_temperature_series_max"] = 99.0 if mismatch else 66.0
    definition["cases"]["second"] = json.loads(json.dumps(case))
    definition["cases"]["second"]["expected"]["return"][0]["bearing_temperature_series_max"] = 66.0
    case_path.write_text(json.dumps(suite), encoding="utf-8")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((240, 24))
    )
    args = (
        str(project),
        "--config",
        str(project / "case-config.toml"),
        "--show",
        "--log-level",
        "warning",
    )

    if mismatch:
        with pytest.raises(SystemExit) as error:
            invoke(monkeypatch, *args)
        assert error.value.code == 1
    else:
        invoke(monkeypatch, *args)

    output = capsys.readouterr().out
    for case_id, fixture in definition["cases"].items():
        status = "failed" if mismatch and case_id == "basic" else "passed"
        section = output.split(f"Case: pump_series/{operator}/{case_id} ({status})\n", 1)[1]
        section = section.split("\nCase:", 1)[0]
        assert "Input: dataset:" in section
        assert "Expected output:" in section
        assert "shape:" not in section
        assert "machine_series_id" in section
        assert "bearing_temperature" in section
        for row in fixture["inputs"]["dataset"]:
            assert str(row["bearing_temperature"]) in section
        assert "bearing_temperature_series_max" in section
        assert str(fixture["expected"]["return"][0]["bearing_temperature_series_max"]) in section
        if status == "failed":
            assert "Actual output:" in section
            assert "! 99.0" in section
            assert "! 66.0" in section
        else:
            assert "Actual output:" not in section

    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    assert report["version"] == 4
    assert report["status"] == ("failed" if mismatch else "passed")
    saved = json.loads(
        (project / "artifacts" / "test" / "cases" / case_path.name).read_text(encoding="utf-8")
    )
    for item in report["cases"]:
        fixture = definition["cases"][item["case"]]
        details = saved[operator]["cases"][item["case"]]
        assert details["inputs"] == fixture["inputs"]
        assert details["expected"] == fixture["expected"]
        assert details["actual"] == [
            {"machine_series_id": "S1", "bearing_temperature_series_max": 66.0}
        ]


def test_show_displays_multiple_inputs_and_empty_output_without_truncation(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    long_value = "x" * 100
    case = models.Case.model_validate(
        {
            "inputs": {
                "first": [{"name": long_value, "values": list(range(8))}],
                "second": [{"value": "second"}],
            },
            "expected": {"return": []},
        }
    )
    result = models.CaseResult(profile="p", operator="o", case="c", status="passed")

    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((200, 24))
    )
    with pl.Config(tbl_cols=1, tbl_rows=1, fmt_str_lengths=5):
        test_display.show_case(result, case, None)

    output = capsys.readouterr().out
    assert "Input: first:" in output
    assert "Input: second:" in output
    assert long_value in output
    assert "[0, 1, 2, 3, 4, 5, 6, 7]" in output
    assert "Expected output:\n(no rows)" in output


def test_show_wide_data_wraps_without_losing_values(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    value = "x" * 100
    case = models.Case.model_validate(
        {
            "inputs": {"dataset": [{"long_column_name": value, "other": "å\nvalue"}]},
            "expected": {"return": [{"long_column_name": value}]},
        }
    )
    result = models.CaseResult(profile="p", operator="o", case="c", status="passed")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((40, 24))
    )

    test_display.show_case(result, case, None)

    output = capsys.readouterr().out
    assert all(len(line) <= 40 for line in output.splitlines())
    assert "Row 1" not in output
    assert output.count("row |") >= 2
    assert "".join(re.findall(r"x{2,}", output)) == value * 2
    assert r"\u00e5\nvalue" in output


def test_show_places_input_and_expected_side_by_side_when_they_fit(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = models.Case.model_validate(
        {
            "inputs": {"dataset": [{"x": 1}, {"x": 3}, {"x": 2}]},
            "expected": {"return": [{"max": 3}]},
        }
    )
    result = models.CaseResult(profile="p", operator="o", case="c", status="passed")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((80, 24))
    )

    test_display.show_case(result, case, None)

    lines = capsys.readouterr().out.splitlines()
    assert any("independent row sets" in line for line in lines)
    assert any("Input: dataset:" in line and "Expected output:" in line for line in lines)
    assert any(line.startswith("3 ") for line in lines)


def test_show_wide_tables_split_columns_and_repeat_rows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = models.Case.model_validate(
        {
            "inputs": {
                "dataset": [
                    {"first_column": "a", "second_column": 1, "third_column": 11},
                    {"first_column": "b", "second_column": 2, "third_column": 22},
                ]
            },
            "expected": {"return": []},
        }
    )
    result = models.CaseResult(profile="p", operator="o", case="c", status="passed")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((30, 24))
    )

    test_display.show_case(result, case, None)

    lines = capsys.readouterr().out.splitlines()
    assert all(len(line) <= 30 for line in lines)
    assert sum(line.startswith("row |") for line in lines) >= 2
    assert sum(line.startswith("1   |") for line in lines) >= 2
    assert sum(line.startswith("2   |") for line in lines) >= 2
    assert all(any(name in line for line in lines) for name in case.inputs["dataset"][0])


def test_show_marks_differences_using_comparison_tolerance(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = models.Case.model_validate(
        {
            "inputs": {"dataset": [{"x": 1}]},
            "expected": {"return": [{"close": 1.0, "different": 3.0, "missing": 8}]},
        }
    )
    actual = pl.DataFrame({"close": [1.000001], "different": [4.0], "extra": [9]})
    result = models.CaseResult(profile="p", operator="o", case="c", status="failed")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((120, 24))
    )

    test_display.show_case(result, case, actual)

    output = capsys.readouterr().out
    comparison = output.split("Comparison", 1)[1]
    assert "! 3.0" in comparison
    assert "! 4.0" in comparison
    assert "! 8" in comparison
    assert "! 9" in comparison
    assert "! 1.0" not in comparison
    assert all(len(line) <= 120 for line in output.splitlines())


def test_show_marks_unexpected_rows(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    case = models.Case.model_validate(
        {"inputs": {"dataset": [{"x": 1}]}, "expected": {"return": []}}
    )
    result = models.CaseResult(profile="p", operator="o", case="c", status="failed")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((80, 24))
    )

    test_display.show_case(result, case, pl.DataFrame({"x": [1, 2]}))

    comparison = capsys.readouterr().out.split("Comparison", 1)[1]
    assert "(no rows)" in comparison
    assert "! 1" in comparison
    assert "! 2" in comparison


def test_show_reports_unrenderable_input_and_continues(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    example_project_factory: example_support.ProjectFactory,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    cases = next(iter(suite.values()))["cases"]
    cases["second"] = json.loads(json.dumps(cases["basic"]))
    cases["basic"]["inputs"]["dataset"][1]["bearing_temperature"] = [1, 2]
    case_path.write_text(json.dumps(suite), encoding="utf-8")
    monkeypatch.setattr(
        test_display.shutil, "get_terminal_size", lambda **_: os.terminal_size((200, 24))
    )

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"), "--show")

    assert error.value.code == 1
    output = capsys.readouterr().out
    assert "Cannot display dataframe:" in output
    assert "/second (passed)" in output
    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    assert [case["status"] for case in report["cases"]] == ["error", "passed"]


@pytest.mark.parametrize(
    "invalid", ["duplicate", "missing-input", "unknown-operator", "io", "empty"]
)
def test_invalid_cases_are_reported(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    example_project_factory: example_support.ProjectFactory,
    invalid: str,
) -> None:
    project, case_path, suite = _case_project(tmp_path, example_project_factory)
    if invalid == "duplicate":
        case_path.write_text('{"same": {}, "same": {}}', encoding="utf-8")
    elif invalid == "missing-input":
        next(iter(suite.values()))["cases"]["basic"]["inputs"] = {}
        case_path.write_text(json.dumps(suite), encoding="utf-8")
    elif invalid == "io":
        case_path.write_text(
            json.dumps({"read_pump_series": next(iter(suite.values()))}), encoding="utf-8"
        )
    elif invalid == "empty":
        case_path.write_text("{}", encoding="utf-8")
    else:
        suite["unknown"] = next(iter(suite.values()))
        case_path.write_text(json.dumps(suite), encoding="utf-8")

    with pytest.raises(SystemExit) as error:
        invoke(monkeypatch, str(project), "--config", str(project / "case-config.toml"))

    assert error.value.code == 1
    report = json.loads((project / "artifacts" / "test" / "test.json").read_text(encoding="utf-8"))
    if invalid == "missing-input":
        assert report["status"] == "failed"
        assert report["cases"][0]["status"] == "error"
        assert "dataframe inputs" in report["cases"][0]["message"]
    else:
        assert report["status"] == "error"
        expected = {
            "duplicate": "Duplicate",
            "unknown-operator": "unknown",
            "io": "I/O and workflow",
            "empty": "No test cases",
        }[invalid]
        assert expected in report["error"]
