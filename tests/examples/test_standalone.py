"""Exercise a copied example independently of the repository working directory."""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import venv

import pytest


@pytest.mark.parametrize("editable", [False, True])
def test_copied_example_installs_as_package_without_pythonpath(
    tmp_path: pathlib.Path, editable: bool
) -> None:
    source = pathlib.Path(__file__).resolve().parents[2] / "example"
    project = tmp_path / "example"
    shutil.copytree(
        source,
        project,
        ignore=shutil.ignore_patterns("_generated", "__pycache__", ".venv", "build", "*.egg-info"),
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment_path = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(environment_path)
    executable_dir = environment_path / ("Scripts" if os.name == "nt" else "bin")
    python = executable_dir / ("python.exe" if os.name == "nt" else "python")
    subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-deps",
            *(["-e"] if editable else []),
            str(project),
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=90,
    )
    run_directory = tmp_path / "run"
    run_directory.mkdir()
    result = subprocess.run(
        [
            str(python),
            "-c",
            "import json, sysconfig, example, example.src, example.spec.profiles; "
            "print(json.dumps([sysconfig.get_paths()['purelib'], example.__file__]))",
        ],
        cwd=run_directory,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )

    purelib, package_file = json.loads(result.stdout)
    expected = project if editable else pathlib.Path(purelib) / "example"
    assert pathlib.Path(package_file).resolve() == expected / "__init__.py"


def test_repository_editable_install_exposes_example(tmp_path: pathlib.Path) -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-c", "import example; print(example.__file__)"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert pathlib.Path(result.stdout.strip()).resolve() == (
        pathlib.Path(__file__).resolve().parents[2] / "example/__init__.py"
    )
