import pathlib

import polars as pl
import pytest

from uptimely import plan
from uptimely.engine.runtime import bindings as bindings_module
from uptimely.engine.runtime import state as state_module


def _bindings(
    *,
    values: dict[str, object] | None = None,
    parameters: dict[str, object] | None = None,
    paths: dict[str, str] | None = None,
    project_root: pathlib.Path | None = None,
) -> bindings_module.RuntimeBindings:
    return bindings_module.RuntimeBindings(
        state_module.RuntimeState(values={} if values is None else values),
        {} if parameters is None else parameters,
        paths=paths,
        project_root=project_root,
    )


def test_runtime_bindings_resolve_nested_results_parameters_and_paths(
    tmp_path: pathlib.Path,
) -> None:
    frame = pl.DataFrame({"asset_id": ["A"]})
    bindings = _bindings(
        values={"$fragments.pump.read": frame, "$datasets.pump.empty": None},
        parameters={"limit": 7, "optional": None},
        paths={"source": "data/input.csv"},
        project_root=tmp_path,
    )

    assert bindings.resolve_value(
        {
            "frames": ["$fragments.pump.read", "$datasets.pump.empty"],
            "options": {"limit": "$params.limit", "optional": "$params.optional"},
            "source": "$paths.source",
            "literal": [None, 1],
        }
    ) == {
        "frames": [frame, None],
        "options": {"limit": 7, "optional": None},
        "source": str(tmp_path / "data/input.csv"),
        "literal": [None, 1],
    }


@pytest.mark.parametrize(
    ("reference", "message"),
    [
        ("$fragments.pump.missing", "Return is unavailable"),
        ("$params.missing", "Unresolved parameter: missing"),
        ("$paths.missing", "Unresolved path: missing"),
    ],
)
def test_runtime_bindings_reject_unavailable_references(reference: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        _bindings().resolve_value(reference)


def test_runtime_bindings_resolve_absolute_paths_without_a_project_root() -> None:
    bindings = _bindings(paths={"source": "/shared/input.csv"})

    assert bindings.resolve_value("$paths.source") == "/shared/input.csv"


def test_runtime_bindings_require_a_project_root_for_relative_paths() -> None:
    bindings = _bindings(paths={"source": "data/input.csv"})

    with pytest.raises(ValueError, match="without a project root"):
        bindings.resolve_value("$paths.source")


def test_runtime_bindings_resolve_invocation_arguments_recursively() -> None:
    frame = pl.DataFrame({"value": [1]})
    invocation = plan.Invocation(
        id="consume",
        entrypoint="test:consume",
        arguments={"data": {"frames": ["$datasets.pump.read"], "threshold": "$params.limit"}},
        returns=None,
    )
    bindings = _bindings(
        values={"$datasets.pump.read": frame},
        parameters={"limit": 5},
    )

    assert bindings.resolve_args(invocation) == {"data": {"frames": [frame], "threshold": 5}}
