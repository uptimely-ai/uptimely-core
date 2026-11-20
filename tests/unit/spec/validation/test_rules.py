import inspect
import typing

import pytest

from uptimely.spec import model
from uptimely.spec.validation import spec as validation
from uptimely.spec.validation.rules import (
    bindings,
    dimensions,
    features,
    profile_identity,
    profiles,
    row_context,
)
from uptimely.spec.validation.rules import functions as function_rules
from uptimely.spec.validation.rules.operators import contracts as operator_contracts
from uptimely.spec.validation.rules.operators import dependencies
from uptimely.spec.validation.rules.operators import inputs as operator_inputs
from uptimely.spec.validation.rules.operators import outputs as operator_outputs

OPERATOR_CASES = ("read", "write", "escape", "conform", "expand", "collapse", "vectorize")


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
    input_dataset = "source" if kind in {"collapse", "conform", "expand"} else "target"
    binding_args = (
        {} if kind in {"read", "escape"} else {"data": f"$profiles.{input_dataset}.dataset"}
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


def target(spec: model.Spec) -> model.Profile:
    return spec.profiles["target"]


def compute(spec: model.Spec) -> model.Operator:
    return target(spec).assembly["compute"]


def test_dimension_change_uses_dimension_identities_not_cardinality() -> None:
    spec = make_spec("conform")
    spec.dimensions["other"] = model.Dimension(
        id="other",
        resolutions={"other": model.Resolution(id="other", key="other", type="integer")},
    )
    spec.profiles["source"].grain[1] = model.Grain(dimension="other", resolution="other")
    assert len(spec.profiles["source"].dimension_ids) == len(spec.profiles["target"].dimension_ids)

    with pytest.raises(ValueError, match="unrelated grain relationship"):
        operator_contracts.validate_dimension_change(spec)

    key = ("target", "compute")
    assert spec.operators_by_key[key].grain_relationships(spec, key)["source"] == "unrelated"


@pytest.mark.parametrize(
    "validate",
    [
        validate
        for _, group in validation.VALIDATION_GROUPS
        for validate in group
        if validate is not operator_outputs.warn_unproduced_features
    ],
    ids=lambda validate: f"{validate.__module__.rsplit('.', 1)[-1]}.{validate.__name__}",
)
def test_atomic_rules_accept_spec_and_do_not_mutate(
    validate: validation.Validator,
) -> None:
    spec = make_spec()
    before = spec.model_dump()
    assert validate(spec) is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", OPERATOR_CASES)
def test_full_validation_preserves_valid_operator_declarations(kind: str) -> None:
    spec = make_spec(kind)
    before = spec.model_dump()
    assert validation.validate_spec(spec) is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", OPERATOR_CASES)
def test_source_discovery_visits_each_operator_declaration(kind: str) -> None:
    spec = make_spec(kind)
    before = spec.model_dump()
    sources = spec.input_sources
    assert list(sources) == [key for key, _ in spec.operator_items]
    key = ("target", "compute")
    source = sources[key]
    if kind == "read":
        assert spec.input_candidates[key] == ()
        assert source is None
    else:
        expected = "target" if kind in {"vectorize", "write"} else "source"
        assert source is not None
        assert source == expected
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", OPERATOR_CASES)
@pytest.mark.parametrize(
    "inputs",
    [[], ["machine"], ["missing"], ["s", "x"], ["s", "missing"]],
)
def test_source_discovery_preserves_unresolved_inputs_for_every_declaration(
    kind: str, inputs: list[str]
) -> None:
    spec = make_spec(kind)
    compute(spec).interface.inputs = [f"$features.{feature}" for feature in inputs]
    before = spec.model_dump()
    key = ("target", "compute")
    assert [feature for feature, _ in spec.input_candidates[key]] == [
        feature for feature in inputs if feature not in spec.identifier_ids
    ]
    assert spec.input_sources[key] is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", OPERATOR_CASES)
def test_source_discovery_does_not_choose_an_ambiguous_owner(kind: str) -> None:
    spec = make_spec(kind)
    source = spec.profiles["source"]
    duplicate = source.model_copy(update={"id": "duplicate"}, deep=True)
    spec.profiles["duplicate"] = duplicate
    compute(spec).interface.inputs = ["$features.s"]
    key = ("target", "compute")
    assert [owner for _, owners in spec.input_candidates[key] for owner in owners] == [
        "source",
        "duplicate",
    ]
    assert spec.input_sources[key] is None


def test_every_rule_is_registered_in_one_validation_group() -> None:
    modules = (
        operator_contracts,
        operator_inputs,
        operator_outputs,
        bindings,
        profile_identity,
        dependencies,
        dimensions,
        features,
        function_rules,
        profiles,
        row_context,
    )
    rules = {
        function
        for module in modules
        for name, function in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("validate_")
    }
    grouped_rules = [
        validate
        for _, group in validation.VALIDATION_GROUPS
        for validate in group
        if validate is not operator_outputs.warn_unproduced_features
    ]
    assert len(grouped_rules) == len(set(grouped_rules))
    assert rules == set(grouped_rules)
    for validate in rules:
        assert list(inspect.signature(validate).parameters) == ["spec"]


def test_runner_runs_validation_groups_in_order(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = make_spec()
    seen: list[str] = []

    def first(document: model.Spec) -> None:
        assert document is spec
        seen.append("first")

    def second(document: model.Spec) -> None:
        assert document is spec
        seen.append("second")

    def third(document: model.Spec) -> None:
        assert document is spec
        seen.append("third")

    monkeypatch.setattr(
        validation,
        "VALIDATION_GROUPS",
        (("first group", (first, second)), ("next", (third,))),
    )
    validation.validate_spec(spec)
    assert seen == ["first", "second", "third"]
