import typing

import pytest

from uptimely.spec import model
from uptimely.spec.validation import spec as validation


def make_spec(kind: str = "vectorize") -> model.Spec:
    """Build a valid document without invoking semantic validation."""
    source_grain = (
        [{"dimension": "machine", "resolution": "machine"}]
        if kind == "expand"
        else [
            {"dimension": "machine", "resolution": "machine"},
            {"dimension": "time", "resolution": "time"},
        ]
    )
    target_grain = (
        [{"dimension": "machine", "resolution": "machine"}]
        if kind == "collapse"
        else [
            {"dimension": "machine", "resolution": "machine"},
            {"dimension": "time", "resolution": "time"},
        ]
    )
    args = {} if kind in {"read", "escape"} else {"data": {"type": "dataframe"}}
    input_profile = "source" if kind in {"collapse", "conform", "expand"} else "target"
    binding_args = (
        {} if kind in {"read", "escape"} else {"data": f"$profiles.{input_profile}.dataset"}
    )
    inputs = (
        []
        if kind == "read"
        else ["$features.s"]
        if kind in {"collapse", "conform", "expand", "escape"}
        else ["$features.x"]
    )
    document: dict[str, typing.Any] = {
        "dimensions": {
            "machine": {"resolutions": {"machine": {"key": "machine", "type": "integer"}}},
            "time": {"resolutions": {"time": {"key": "time", "type": "datetime"}}},
        },
        "functions": {
            "read": {
                "returns": "dataframe",
                "entrypoint": "not_imported:read",
            },
            "compute": {
                "returns": (
                    "none" if kind == "write" else "any" if kind == "escape" else "dataframe"
                ),
                "entrypoint": "not_imported:compute",
                "args": args,
            },
        },
        "profiles": {
            "source": {
                "grain": source_grain,
                "features": {
                    "machine": {},
                    **({"time": {}} if len(source_grain) > 1 else {}),
                    "s": {},
                },
                "order": [{"dimension": "machine", "resolution": "machine", "direction": "asc"}],
                "assembly": {
                    "read_source": {
                        "compute": {"function": "read"},
                        "interface": {
                            "outputs": [
                                "$features.s",
                            ]
                        },
                    }
                },
            },
            "target": {
                "grain": target_grain,
                "features": {
                    "machine": {},
                    **({"time": {}} if len(target_grain) > 1 else {}),
                    "x": {},
                    **({} if kind in {"write", "escape"} else {"y": {}}),
                },
                "order": [{"dimension": "machine", "resolution": "machine", "direction": "asc"}],
                "assembly": {
                    "read_base": {
                        "compute": {"function": "read"},
                        "interface": {
                            "outputs": [
                                "$features.x",
                            ]
                        },
                    },
                    "compute": {
                        "compute": {"function": "compute", "args": binding_args},
                        "interface": {
                            "inputs": inputs,
                            "outputs": ([] if kind in {"write", "escape"} else ["$features.y"]),
                        },
                    },
                },
            },
        },
    }
    return model.Spec.model_validate(document)


def test_failed_check_stops_runner_and_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def first(spec: model.Spec) -> None:
        seen.append("first")
        raise ValueError("invalid prerequisite")

    def dependent(spec: model.Spec) -> None:
        pytest.fail("A dependent validator must not run")

    def warn(spec: model.Spec) -> None:
        pytest.fail("Warnings must not be emitted for invalid specs")

    monkeypatch.setattr(
        validation,
        "VALIDATION_GROUPS",
        (("first group", (first,)), ("later group", (dependent,)), ("warnings", (warn,))),
    )
    with pytest.raises(ValueError, match="invalid prerequisite"):
        validation.validate_spec(make_spec())
    assert seen == ["first"]
