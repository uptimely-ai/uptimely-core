"""Verify the example's operator cases against the saved build."""

import json
import pathlib

from support import examples as example_support

from uptimely import application
from uptimely.test import runner

CASE_DIR = example_support.REPOSITORY_ROOT / "example" / "tests" / "uptimely"


def test_example_operator_cases(example_bundle_factory: example_support.BundleFactory) -> None:
    bundle = example_bundle_factory()
    files = {path.stem: path for path in CASE_DIR.glob("*.json")}
    assert set(files) == set(bundle.spec_definition.profiles)
    for profile_id, path in files.items():
        suite = json.loads(path.read_text(encoding="utf-8"))
        invocations = [
            invocation
            for invocation in bundle.execution_plan.invocations
            if invocation.semantics is not None
            and invocation.semantics.profile_id == profile_id
            and invocation.semantics.role == "compute"
            and bundle.spec_definition.functions.root[invocation.semantics.function_id].category
            not in runner.EXCLUDED_CATEGORIES
        ]
        operators = [
            invocation.semantics.operator_id
            for invocation in invocations
            if invocation.semantics is not None
        ]
        assert len(set(operators)) == len(operators)
        assert set(suite) == set(operators)
        assert all(operator["cases"] for operator in suite.values())


def test_example_cases_run_from_saved_build(
    tmp_path: pathlib.Path, example_project_factory: example_support.ProjectFactory
) -> None:
    root = example_project_factory(tmp_path / "example")
    report = runner.TestRunner(application.Uptimely(root)).run()

    assert report.status == "passed"
    assert report.cases
    assert all(case.status == "passed" for case in report.cases)
    saved = json.loads((root / runner.REPORT_PATH).read_text(encoding="utf-8"))
    assert saved["status"] == "passed"
    assert len(saved["cases"]) == len(report.cases)
