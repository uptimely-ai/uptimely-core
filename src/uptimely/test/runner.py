"""Run isolated dataframe cases against an existing project build."""

import datetime
import json
import math
import pathlib
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

from . import models, store

REPORT_PATH = paths.TEST_REPORT_FILE
EXCLUDED_CATEGORIES = frozenset({"read", "write", "workflow"})
JSON_VALUE = pydantic.TypeAdapter(pydantic.JsonValue)
CASE_INPUT_PREFIX = "$"


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
        artifacts = store.TestStore(self.app.root)
        artifacts.save_report(report)
        try:
            folder = self.app.root / self.app.config.test.path
            if not folder.is_dir():
                raise FileNotFoundError(
                    f"Configured test folder {self.app.config.test.path} not found"
                )
            if folder.resolve() == (self.app.root / paths.TEST_CASES_DIR).resolve():
                raise ValueError("The test source folder cannot be the case artifact folder")
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
                artifacts.save_cases(report)
                self._remove_legacy_data(folder)
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
            artifacts.save_report(report)
            raise
        report.finished_at = datetime.datetime.now(datetime.UTC)
        artifacts.save_report(report)
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

    def _remove_legacy_data(self, source: pathlib.Path) -> None:
        """Remove old copied JSON artifacts without removing source case files."""
        folder = self.app.root / paths.TEST_OUTPUT_DIR / "data"
        if folder.is_symlink() or source.resolve().is_relative_to(folder.resolve()):
            return
        if folder.is_dir():
            for path in folder.glob("*.json"):
                path.unlink()
            if not any(folder.iterdir()):
                folder.rmdir()

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
            profile=profile, operator=operator, case=case_id, status="passed", data=case
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
            frames: dict[int, str] = {}
            for name, reference in dataframe_args.items():
                rows = case.inputs[name]
                if not rows or any(set(row) != set(rows[0]) for row in rows):
                    raise ValueError(f"Input {name} must have nonempty rows with matching columns")
                frame = pl.DataFrame(rows).lazy()
                frames[id(frame)] = name
                runtime_state.store(reference, frame)
            executor = execution.InvocationExecutor(
                entries,
                self.app.config.params.root,
                runtime_state,
                paths={},
                project_root=self.app.root,
            )
            arguments = executor.resolve_arguments(invocation)
            result.call = self._resolved_call(invocation.entrypoint, arguments, frames)
            actual = executor.execute(invocation, arguments)
            if not isinstance(actual, (pl.LazyFrame, pl.DataFrame)):
                raise TypeError("Compute binding did not return a dataframe")
            frame = actual.collect() if isinstance(actual, pl.LazyFrame) else actual
            result.actual = self._frame_rows(frame)
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
    def _resolved_call(
        function: str, arguments: dict[str, object], frames: dict[int, str]
    ) -> models.ResolvedCall:
        dataframe_inputs: dict[str, str] = {}

        def encode(value: object, pointer: str) -> pydantic.JsonValue:
            if isinstance(value, (pl.LazyFrame, pl.DataFrame)):
                if id(value) not in frames:
                    raise ValueError(f"Resolved dataframe at {pointer} is not a case input")
                dataframe_inputs[pointer] = frames[id(value)]
                return f"{CASE_INPUT_PREFIX}{frames[id(value)]}"
            if isinstance(value, list):
                return [encode(item, f"{pointer}/{index}") for index, item in enumerate(value)]
            if isinstance(value, dict):
                encoded_object: dict[str, pydantic.JsonValue] = {}
                for key, item in value.items():
                    if not isinstance(key, str):
                        raise TypeError("Resolved argument object keys must be strings")
                    encoded_object[key] = encode(
                        item, f"{pointer}/{key.replace('~', '~0').replace('/', '~1')}"
                    )
                return encoded_object
            if isinstance(value, float) and not math.isfinite(value):
                raise ValueError(f"Non-finite resolved argument at {pointer}")
            return JSON_VALUE.validate_python(value, strict=True)

        encoded = {
            name: encode(value, f"/{name.replace('~', '~0').replace('/', '~1')}")
            for name, value in arguments.items()
        }
        return models.ResolvedCall(
            function=function, arguments=encoded, dataframe_inputs=dataframe_inputs
        )

    @staticmethod
    def _compare(actual: pl.DataFrame, expected: list[dict[str, pydantic.JsonValue]]) -> None:
        if not expected:
            if actual.height:
                raise AssertionError("Expected no rows")
            return
        if any(set(row) != set(expected[0]) for row in expected):
            raise ValueError("Expected rows must have matching columns")

        rows = TestRunner._frame_rows(actual)
        pl_testing.assert_frame_equal(
            pl.DataFrame(rows), pl.DataFrame(expected), check_dtypes=False, check_column_order=False
        )

    @staticmethod
    def _frame_rows(frame: pl.DataFrame) -> list[dict[str, pydantic.JsonValue]]:
        def encode(value: object) -> str:
            if isinstance(value, (datetime.date, datetime.datetime)):
                return value.isoformat()
            raise TypeError(f"Unsupported dataframe value: {type(value).__name__}")

        return json.loads(json.dumps(frame.to_dicts(), default=encode, allow_nan=False))
