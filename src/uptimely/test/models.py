"""Models for isolated operator cases and their results."""

import datetime
import typing

import pydantic

from uptimely.run import models as run_models


class _Model(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid", strict=True)


class Expected(_Model):
    """Expected dataframe rows."""

    model_config = pydantic.ConfigDict(populate_by_name=True)

    return_: list[dict[str, pydantic.JsonValue]] = pydantic.Field(alias="return")


class Case(_Model):
    """Dataframe arguments and expected returned rows for one compute binding."""

    inputs: dict[str, list[dict[str, pydantic.JsonValue]]]
    expected: Expected


class OperatorCases(_Model):
    """Named cases for one operator."""

    cases: dict[str, Case] = pydantic.Field(min_length=1)


class ResolvedCall(_Model):
    """Entrypoint and resolved arguments for a case invocation."""

    function: str
    arguments: dict[str, pydantic.JsonValue]
    dataframe_inputs: dict[str, str] = pydantic.Field(default_factory=dict)


class CaseArtifact(Case):
    """Case inputs, outputs, and resolved call saved for a test run."""

    actual: list[dict[str, pydantic.JsonValue]] | None = None
    call: ResolvedCall | None = None


class OperatorCaseArtifacts(_Model):
    """Saved cases for one operator."""

    cases: dict[str, CaseArtifact]


class CaseResult(_Model):
    """Outcome of one operator case."""

    profile: str
    operator: str
    case: str
    status: typing.Literal["passed", "failed", "error"]
    message: str | None = None
    data: Case | None = None
    actual: list[dict[str, pydantic.JsonValue]] | None = None
    call: ResolvedCall | None = None


class TestReport(_Model):
    """Results of one completed or incomplete test run."""

    version: typing.Literal[1, 2, 3, 4] = 4
    started_at: datetime.datetime
    finished_at: datetime.datetime | None = None
    status: typing.Literal["running", "passed", "failed", "error"]
    build: run_models.BuildIdentity | None = None
    cases: list[CaseResult] = pydantic.Field(default_factory=list)
    error: str | None = None
