"""Exercise a copied example independently of the repository working directory."""

import os
import pathlib
import shutil
import subprocess
import sys


def test_copied_example_runs_without_installation_or_pythonpath(tmp_path: pathlib.Path) -> None:
    source = pathlib.Path(__file__).resolve().parents[2] / "example"
    project = tmp_path / "pump-analytics"
    shutil.copytree(
        source,
        project,
        ignore=shutil.ignore_patterns("_generated", "__pycache__", ".venv", "build", "*.egg-info"),
    )
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    for action in ("build", "run"):
        result = subprocess.run(
            [sys.executable, "-m", "uptimely.cli.cli", action, str(project)],
            cwd=tmp_path,
            env=environment,
            capture_output=True,
            text=True,
            timeout=90,
        )
        assert result.returncode == 0, result.stdout + result.stderr
