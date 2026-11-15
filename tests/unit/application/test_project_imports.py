"""Verify project-local imports during builds and runs."""

import pathlib
import sys
import types

import pytest

from uptimely import application, engine
from uptimely.application.build import source as build_source
from uptimely.cli import cli


def _write_project(root: pathlib.Path, value: int) -> None:
    (root / "src/isolated_calc").mkdir(parents=True)
    (root / "spec").mkdir()
    (root / "src/isolated_calc/functions.py").write_text(
        "import polars as pl\n"
        "def read() -> pl.DataFrame:\n"
        f"    return pl.DataFrame({{'value': [{value}]}})\n",
        encoding="utf-8",
    )
    (root / "spec/spec.py").write_text(
        "from isolated_calc import functions\n"
        "import uptimely as up\n"
        "class Values(up.Profile):\n"
        "    id = 'values'\n"
        "    assembly = [up.Operator(\n"
        "        id='read',\n"
        "        outputs=[up.Feature(id='value')],\n"
        "        compute=up.Bind(up.ref.function("
        "functions.read, returns='dataframe')),\n"
        "    )]\n"
        "python_spec = up.Spec(profiles=[Values])\n",
        encoding="utf-8",
    )


def test_build_and_run_isolate_modules_for_distinct_projects(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = tmp_path / "first-project"
    second = tmp_path / "renamed-project"
    _write_project(first, 1)
    _write_project(second, 2)
    (first / "src/uptimely.py").write_text(
        "raise RuntimeError('must not shadow the framework')\n", encoding="utf-8"
    )
    existing = types.ModuleType("isolated_calc")
    monkeypatch.setitem(sys.modules, "isolated_calc", existing)
    original_path = sys.path[:]

    bundles = [application.build(first), application.build(second)]
    for bundle, value in zip(bundles, (1, 2), strict=True):
        result = engine.Engine(bundle).run()
        assert not result.failures
        assert result.datasets["values"].to_dict(as_series=False) == {"value": [value]}
        assert sys.modules["isolated_calc"] is existing
        assert sys.path == original_path


def test_build_and_run_use_configured_source_path(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "project"
    _write_project(root, 7)
    (root / "src").rename(root / "python")

    bundle = application.build(root, src_path=pathlib.Path("python"))
    result = engine.Engine(bundle).run(src_path=pathlib.Path("python"))

    assert not result.failures
    assert result.datasets["values"].to_dict(as_series=False) == {"value": [7]}


def test_uptimely_build_and_run_use_saved_build(tmp_path: pathlib.Path) -> None:
    root = tmp_path / "project"
    _write_project(root, 7)
    app = application.Uptimely(root)
    app.build()
    (root / "spec/spec.py").write_text("raise RuntimeError('must not rebuild')\n", encoding="utf-8")

    result = app.run(validate=True)

    assert not result.failures
    assert result.datasets["values"].to_dict(as_series=False) == {"value": [7]}


def test_cli_run_uses_configured_source_path(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "project"
    _write_project(root, 9)
    (root / "src").rename(root / "python")
    application.build(root, src_path=pathlib.Path("python"))
    (root / "config").mkdir()
    (root / application.CONFIG_FILE).write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["uptimely", "run", str(root), "--src-path", "python"],
    )

    cli.main()

    result = capsys.readouterr()
    assert "Engine processed 1 profiles in " in result.out


def test_configured_source_path_must_be_a_directory(tmp_path: pathlib.Path) -> None:
    with (
        pytest.raises(NotADirectoryError, match="Project source path is not a directory"),
        build_source.project_source_path(tmp_path, pathlib.Path("missing")),
    ):
        pytest.fail("A missing configured source path must fail")


def test_import_state_is_restored_after_build_failure(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_project(tmp_path / "project", 1)
    (tmp_path / "project/spec/spec.py").write_text(
        "import isolated_calc\nraise ValueError('bad specification')\n", encoding="utf-8"
    )
    existing = types.ModuleType("isolated_calc")
    monkeypatch.setitem(sys.modules, "isolated_calc", existing)
    original_path = sys.path[:]

    with pytest.raises(application.ProjectBuildError, match="bad specification"):
        application.build(tmp_path / "project")

    assert sys.modules["isolated_calc"] is existing
    assert sys.path == original_path


@pytest.mark.parametrize("name", ["python_project", "renamed-project"])
def test_build_discovers_spec_in_project_with_root_init(tmp_path: pathlib.Path, name: str) -> None:
    root = tmp_path / name
    _write_project(root, 3)
    (root / "__init__.py").touch()

    result = engine.Engine(application.build(root)).run()

    assert not result.failures
    assert result.datasets["values"].to_dict(as_series=False) == {"value": [3]}
