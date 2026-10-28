"""Run against built wheels in a clean virtualenv, without pytest's conftest."""

import importlib.metadata
import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

import examples
import installed_analytics

import uptimely

REPOSITORY_ROOT = pathlib.Path(__file__).resolve().parents[2]


class InstalledImportsTest(unittest.TestCase):
    """Exercise real console scripts and fresh processes outside the checkout."""

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="uptimely-installed-test-")
        self.addCleanup(temporary.cleanup)
        self.root = pathlib.Path(temporary.name)
        self.environment = os.environ.copy()
        self.environment.pop("PYTHONPATH", None)
        self.environment.pop("PYTHONHOME", None)
        self.environment["PYTHONNOUSERSITE"] = "1"
        executable = pathlib.Path(sys.executable).with_name("uptimely")
        self.assertTrue(executable.is_file(), f"Missing installed console script: {executable}")
        self.executable = executable

    def command(self, *arguments: str, succeeds: bool = True) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [str(self.executable), *arguments],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=90,
            check=False,
        )
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertFalse(result.stderr, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertIn("uptimely: error:", result.stderr)
        return result

    def test_environment_is_not_editable_or_using_the_checkout(self) -> None:
        for module in (uptimely, examples, installed_analytics):
            with self.subTest(module=module.__name__):
                self.assertIsNotNone(module.__file__)
                location = pathlib.Path(module.__file__).resolve()
                self.assertTrue(location.is_relative_to(sys.prefix), str(location))
                self.assertFalse(location.is_relative_to(REPOSITORY_ROOT), str(location))
        for entry in sys.path:
            self.assertFalse(pathlib.Path(entry).resolve().is_relative_to(REPOSITORY_ROOT), entry)
        distribution = importlib.metadata.distribution("uptimely-core")
        direct_url = json.loads(distribution.read_text("direct_url.json") or "{}")
        self.assertFalse(direct_url.get("dir_info", {}).get("editable", False))
        packaged_files = [str(path) for path in distribution.files or []]
        self.assertTrue(any(path.startswith("examples/") for path in packaged_files))
        self.assertFalse(any("/_generated/" in path for path in packaged_files))

    def test_all_examples_build_and_run_from_installed_wheel(self) -> None:
        examples_root = pathlib.Path(examples.__file__).parent
        (self.root / "examples").mkdir()
        shutil.copyfile(examples_root / "__init__.py", self.root / "examples" / "__init__.py")
        for name in ("pump_analytics",):
            with self.subTest(example=name):
                project = self.root / "examples" / name
                shutil.copytree(examples_root / name, project)
                result = self.command("project", "build", "--project-root", str(project))
                self.assertIn("Build files created", result.stdout)
                build = project / "_generated" / "build"
                self.assertTrue((build / "explorer" / "index.html").is_file())
                self.assertTrue((build / "explorer" / "css" / "base.css").is_file())
                self.assertTrue((build / "explorer" / "js" / "feature_lineage.js").is_file())
                plan = json.loads((build / "execution_plan.json").read_text(encoding="utf-8"))
                self.assertTrue(plan["invocations"])
                for package in plan["resources"]["entrypoint_packages"].values():
                    self.assertEqual(package["distribution"], "uptimely-core")
                    self.assertEqual(
                        package["version"], importlib.metadata.version("uptimely-core")
                    )
                result = self.command("run", str(project), "--preview", "2")
                self.assertIn("Engine completed", result.stdout)
                self.assertIn("Dataset:", result.stdout)

    def test_installed_project_builds_and_executes_in_separate_processes(self) -> None:
        project = self.root / "project"
        self.command(
            "build", str(project), "--python-spec", "installed_analytics.declaration:python_spec"
        )
        build = project / "_generated" / "build"
        plan = json.loads((build / "execution_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(
            plan["resources"]["entrypoint_packages"],
            {
                "installed_analytics.functions:Readers.values": {
                    "distribution": "uptimely-import-fixture",
                    "version": "1.2.3",
                }
            },
        )
        config = project / "config" / "config.json"
        config.parent.mkdir()
        config.write_text("{}", encoding="utf-8")
        result = self.command("engine", "run", "--project-root", str(project), "--preview", "2")
        self.assertIn("1 datasets processed", result.stdout)
        self.assertIn("Dataset: values", result.stdout)
        result = subprocess.run(
            [
                sys.executable,
                "-I",
                "-c",
                "import json, pathlib, sys\n"
                "from uptimely import engine, project\n"
                "original_path = sys.path.copy()\n"
                "bundle = project.load_build_bundle(pathlib.Path(sys.argv[1]))\n"
                "result = engine.Engine(bundle, engine.EngineConfig()).run()\n"
                "assert not result.failures, result.failures\n"
                "assert set(result.invocation_statuses.values()) == {'succeeded'}\n"
                "assert sys.path == original_path\n"
                "print(json.dumps(result.datasets['values'].to_dict(as_series=False)))\n",
                str(project),
            ],
            cwd=self.root,
            env=self.environment,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"row": [1, 2], "value": [2, 3]})

        json_project = self.root / "json-project"
        self.command("build", str(json_project), "--json-spec", str(build / "spec.json"))
        result = self.command("run", str(json_project), "--config", str(config), "--preview", "2")
        self.assertIn("Dataset: values", result.stdout)

    def test_missing_runtime_dependency_is_deferred_but_not_hidden(self) -> None:
        project = self.root / "project"
        self.command(
            "build", str(project), "--python-spec", "installed_analytics.declaration:python_spec"
        )
        build = project / "_generated" / "build"
        source = json.loads((build / "spec.json").read_text(encoding="utf-8"))
        function = next(iter(source["functions"].values()))
        function["entrypoint"] = "installed_analytics.unavailable:read"
        function["validate_signature"] = False
        source_path = self.root / "deferred.json"
        source_path.write_text(json.dumps(source), encoding="utf-8")
        self.command("build", str(project), "--json-spec", str(source_path))
        config = self.root / "config.json"
        config.write_text("{}", encoding="utf-8")
        result = self.command("run", str(project), "--config", str(config), succeeds=False)
        self.assertIn("uptimely_missing_runtime_dependency", result.stderr)
        self.assertIn("recorded package provenance: uptimely-import-fixture==1.2.3", result.stderr)
        self.assertIn("available runtime package: uptimely-import-fixture==1.2.3", result.stderr)
        self.assertNotIn("Engine completed", result.stdout)

        function["validate_signature"] = True
        source_path.write_text(json.dumps(source), encoding="utf-8")
        result = self.command(
            "build", str(project), "--json-spec", str(source_path), succeeds=False
        )
        self.assertIn("uptimely_missing_runtime_dependency", result.stderr)
        self.assertIn("available build package: uptimely-import-fixture==1.2.3", result.stderr)


if __name__ == "__main__":
    unittest.main()
