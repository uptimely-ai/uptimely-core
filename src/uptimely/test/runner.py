"""Run isolated dataframe cases against an existing project build."""

import datetime
import json
import os
import pathlib
import shutil
import tempfile
import typing
from collections import abc

import polars as pl
import polars.testing as pl_testing
import pydantic

from uptimely import application, plan
from uptimely.codebase.python import codebase, entrypoint, imports, runtime
from uptimely.engine.runtime import execution, state
from uptimely.project import paths
from uptimely.run import models as run_models

from . import models

REPORT_PATH = paths.TEST_REPORT_FILE
EXCLUDED_CATEGORIES = frozenset({"read", "write", "workflow"})


class TestRunner:
    """Run JSON operator cases using the saved build and current project configuration."""

    def __init__(self, app: application.Uptimely) -> None:
        """Bind the runner to a configured project."""
        self.app = app

    def run(
        self,
        *,
        on_case: abc.Callable[[models.CaseResult, models.Case, pl.DataFrame | None], None]
        | None = None,
    ) -> models.TestReport:
        """Execute all cases and atomically save the latest report.

        Args:
            on_case: Optional callback receiving each outcome, case, and mismatched output.

        Returns:
            The completed report, including individual failures.

        Raises:
            OSError: A required file cannot be read or the report cannot be saved.
            ValueError: Configuration, build, or case definitions are invalid.
        """
        report = models.TestReport(started_at=datetime.datetime.now(datetime.UTC), status="running")
        self._save(report)
        try:
            folder = self.app.root / self.app.config.test.path
            if not folder.is_dir():
                raise FileNotFoundError(
                    f"Configured test folder {self.app.config.test.path} not found"
                )
            self._copy_test_data(folder)
            with self.app.read_build_bundle() as bundle:
                report.build = run_models.BuildIdentity.from_bundle(bundle)
                if bundle.source_path is None:
                    raise ValueError("The saved build has no bundled project source")
                if bundle.requirements_file is not None:
                    runtime.check_compatibility(bundle.requirements_file)
                cases = self._load_cases(folder, bundle)
                if not cases:
                    raise ValueError(f"No test cases found in {folder}")
                entries = codebase.Codebase.from_locations(
                    bundle.execution_plan.entrypoints, entrypoint_type=entrypoint.Entrypoint
                ).entrypoints_index
                with imports.PythonModuleImportManager(
                    bundle.root, bundle.source_path, reserved_modules=("uptimely",)
                ).expose():
                    for profile, operator, case_id, invocation, case in cases:
                        result, actual = self._run_case(
                            profile, operator, case_id, invocation, case, entries
                        )
                        report.cases.append(result)
                        if on_case is not None:
                            on_case(result, case, actual)
                report.status = (
                    "passed" if all(case.status == "passed" for case in report.cases) else "failed"
                )
        except (
            application.BuildError,
            application.BuildLockError,
            OSError,
            ValueError,
            TypeError,
        ) as error:
            report.status = "error"
            report.error = f"{type(error).__name__}: {error}"
            report.finished_at = datetime.datetime.now(datetime.UTC)
            self._save(report)
            raise
        report.finished_at = datetime.datetime.now(datetime.UTC)
        self._save(report)
        return report

    def _load_cases(
        self, folder: pathlib.Path, bundle: application.BuildBundle
    ) -> list[tuple[str, str, str, plan.Invocation, models.Case]]:
        invocations: dict[tuple[str, str], list[plan.Invocation]] = {}
        for invocation in bundle.execution_plan.invocations:
            semantics = invocation.semantics
            if semantics is not None and semantics.profile_id and semantics.role == "compute":
                invocations.setdefault((semantics.profile_id, semantics.operator_id), []).append(
                    invocation
                )
        cases: list[tuple[str, str, str, plan.Invocation, models.Case]] = []
        for path in sorted(folder.glob("*.json")):
            if path.stem not in bundle.spec_definition.profiles:
                raise ValueError(f"Unknown test profile: {path.stem}")
            try:
                raw = json.loads(
                    path.read_text(encoding="utf-8"),
                    object_pairs_hook=self._unique_keys,
                    parse_constant=self._invalid_constant,
                )
                suites = pydantic.TypeAdapter(dict[str, models.OperatorCases]).validate_python(raw)
            except (ValueError, TypeError) as error:
                raise ValueError(f"Invalid test file {path}: {error}") from error
            for operator, suite in suites.items():
                matches = invocations.get((path.stem, operator), [])
                if len(matches) != 1:
                    raise ValueError(
                        f"Expected one compute binding for {path.stem}/{operator}, "
                        f"found {len(matches)}"
                    )
                invocation = matches[0]
                semantics = invocation.semantics
                assert semantics is not None
                category = bundle.spec_definition.functions.root[semantics.function_id].category
                if (
                    category in EXCLUDED_CATEGORIES
                    or semantics.is_sink
                    or semantics.is_workflow
                    or semantics.dataframe_input_scope == "none"
                ):
                    raise ValueError(
                        f"I/O and workflow cases are not supported: {path.stem}/{operator}"
                    )
                for case_id, case in suite.cases.items():
                    if not case_id:
                        raise ValueError(f"Empty case ID in {path}")
                    cases.append((path.stem, operator, case_id, invocation, case))
        return cases

    def _copy_test_data(self, folder: pathlib.Path) -> None:
        """Copy the current JSON case files to the test artifact directory."""
        target = self.app.root / paths.TEST_DATA_DIR
        source_files = sorted(folder.glob("*.json"))
        source_names = {path.name for path in source_files}
        target.mkdir(parents=True, exist_ok=True)
        for stale_file in target.glob("*.json"):
            if stale_file.name not in source_names:
                stale_file.unlink()
        for source in source_files:
            shutil.copy2(source, target / source.name)

    @staticmethod
    def _unique_keys(pairs: list[tuple[str, typing.Any]]) -> dict[str, typing.Any]:
        result: dict[str, typing.Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key}")
            result[key] = value
        return result

    @staticmethod
    def _invalid_constant(value: str) -> typing.NoReturn:
        raise ValueError(f"Non-finite JSON value: {value}")

    def _run_case(
        self,
        profile: str,
        operator: str,
        case_id: str,
        invocation: plan.Invocation,
        case: models.Case,
        entries: abc.Mapping[str, entrypoint.Entrypoint],
    ) -> tuple[models.CaseResult, pl.DataFrame | None]:
        result = models.CaseResult(
            profile=profile, operator=operator, case=case_id, status="passed"
        )
        mismatch: pl.DataFrame | None = None
        try:
            runtime_state = state.RuntimeState()
            dataframe_args = {
                name: value
                for name, value in invocation.arguments.items()
                if isinstance(value, str) and value.startswith(plan.Variable.PREFIXES)
            }
            if set(case.inputs) != set(dataframe_args):
                raise ValueError(f"Expected dataframe inputs: {', '.join(sorted(dataframe_args))}")
            for name, reference in dataframe_args.items():
                rows = case.inputs[name]
                if not rows or any(set(row) != set(rows[0]) for row in rows):
                    raise ValueError(f"Input {name} must have nonempty rows with matching columns")
                runtime_state.store(reference, pl.DataFrame(rows).lazy())
            executor = execution.InvocationExecutor(
                entries,
                self.app.config.params.root,
                runtime_state,
                paths={},
                project_root=self.app.root,
            )
            actual = executor.execute(invocation, executor.resolve_arguments(invocation))
            if not isinstance(actual, (pl.LazyFrame, pl.DataFrame)):
                raise TypeError("Compute binding did not return a dataframe")
            frame = actual.collect() if isinstance(actual, pl.LazyFrame) else actual
            try:
                self._compare(frame, case.expected.return_)
            except AssertionError:
                result.status = "failed"
                result.message = "Returned dataframe does not match expected rows"
                mismatch = frame
        except Exception as error:
            result.status = "error"
            result.message = f"{type(error).__name__}: {str(error)[:500]}"
        return result, mismatch

    @staticmethod
    def _compare(actual: pl.DataFrame, expected: list[dict[str, pydantic.JsonValue]]) -> None:
        if not expected:
            if actual.height:
                raise AssertionError("Expected no rows")
            return
        if any(set(row) != set(expected[0]) for row in expected):
            raise ValueError("Expected rows must have matching columns")

        def encode(value: object) -> str:
            if isinstance(value, (datetime.date, datetime.datetime)):
                return value.isoformat()
            raise TypeError(f"Unsupported dataframe value: {type(value).__name__}")

        rows = json.loads(json.dumps(actual.to_dicts(), default=encode, allow_nan=False))
        pl_testing.assert_frame_equal(
            pl.DataFrame(rows), pl.DataFrame(expected), check_dtypes=False, check_column_order=False
        )

    def _save(self, report: models.TestReport) -> None:
        path = self.app.root / REPORT_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary: pathlib.Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=path.parent, prefix=".test-", delete=False
            ) as file:
                temporary = pathlib.Path(file.name)
                file.write(report.model_dump_json(indent=2) + "\n")
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
