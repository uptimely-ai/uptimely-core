"""Read and write test reports and per-profile case artifacts."""

import os
import pathlib
import tempfile

import pydantic

from uptimely.project import paths

from . import models

CASE_ARTIFACTS = pydantic.TypeAdapter(dict[str, models.OperatorCaseArtifacts])
REPORT_DETAILS = {"cases": {"__all__": {"data", "actual", "call"}}}


class TestStore:
    """Manage the latest test report and its case details."""

    def __init__(self, root: pathlib.Path) -> None:
        self.root = root

    @staticmethod
    def report_json(report: models.TestReport) -> str:
        """Serialize current reports without embedded case details."""
        if report.version >= 4:
            return report.model_dump_json(indent=2, by_alias=True, exclude=REPORT_DETAILS)
        return report.model_dump_json(indent=2, by_alias=True)

    def read_report(self) -> models.TestReport:
        """Read and validate the latest report."""
        return models.TestReport.model_validate_json(
            (self.root / paths.TEST_REPORT_FILE).read_bytes()
        )

    def read_cases(
        self, report: models.TestReport, profile: str
    ) -> dict[str, models.OperatorCaseArtifacts]:
        """Read a profile's case details and verify the referenced cases."""
        expected = {(case.operator, case.case) for case in report.cases if case.profile == profile}
        if not expected:
            raise KeyError(f"No test cases for profile: {profile}")
        if profile in {".", ".."} or "/" in profile or "\\" in profile:
            raise ValueError(f"Invalid test profile: {profile!r}")
        path = self.root / paths.TEST_CASES_DIR / f"{profile}.json"
        cases = CASE_ARTIFACTS.validate_json(path.read_bytes(), strict=True)
        found = {(operator, case) for operator, suite in cases.items() for case in suite.cases}
        if found != expected:
            raise ValueError(f"Saved test cases do not match report for profile: {profile}")
        return cases

    def save_cases(self, report: models.TestReport) -> None:
        """Save case details grouped by profile and remove stale profile artifacts."""
        profiles: dict[str, dict[str, models.OperatorCaseArtifacts]] = {}
        for result in report.cases:
            if result.data is None:
                raise ValueError(f"Missing test case data: {result.profile}/{result.operator}")
            suite = profiles.setdefault(result.profile, {}).setdefault(
                result.operator, models.OperatorCaseArtifacts(cases={})
            )
            suite.cases[result.case] = models.CaseArtifact(
                inputs=result.data.inputs,
                expected=result.data.expected,
                actual=result.actual,
                call=result.call,
            )
        folder = self.root / paths.TEST_CASES_DIR
        folder.mkdir(parents=True, exist_ok=True)
        for profile, suites in profiles.items():
            if profile in {".", ".."} or "/" in profile or "\\" in profile:
                raise ValueError(f"Invalid test profile: {profile!r}")
            self._write(
                folder / f"{profile}.json",
                CASE_ARTIFACTS.dump_json(suites, indent=2, by_alias=True).decode("utf-8") + "\n",
            )
        names = {f"{profile}.json" for profile in profiles}
        for path in folder.glob("*.json"):
            if path.name not in names:
                path.unlink()

    def save_report(self, report: models.TestReport) -> None:
        """Atomically save a report."""
        self._write(self.root / paths.TEST_REPORT_FILE, self.report_json(report) + "\n")

    @staticmethod
    def _write(path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: pathlib.Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=".test-", delete=False
            ) as file:
                temporary = pathlib.Path(file.name)
                file.write(content)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
