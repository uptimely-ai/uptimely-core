import copy
import pathlib

import pytest

from uptimely import compiler, plan, spec
from uptimely.plan import models
from uptimely.spec import model as spec_model


def _payload() -> dict:
    return {
        "plan_version": plan.PLAN_VERSION,
        "required_backend": "polars",
        "invocations": [
            {
                "id": "read",
                "entrypoint": "example:read",
                "arguments": {"path": "$paths.input", "label": "pressure"},
                "returns": "$fragments.pump.read",
            },
            {
                "id": "merge",
                "entrypoint": "example:merge",
                "arguments": {
                    "data": {
                        "frames": ["$fragments.pump.read", None],
                        "limit": "$params.limit",
                    }
                },
                "returns": "$dataset.pump.merge",
            },
            {
                "id": "write",
                "entrypoint": "example:write",
                "arguments": {"data": "$dataset.pump.merge"},
                "returns": None,
            },
        ],
        "stages": [["read"], ["merge"], ["write"]],
        "datasets": {"pump": "$dataset.pump.merge"},
    }


def test_round_trips_explicit_arguments_and_returns() -> None:
    original = plan.from_dict(_payload())
    restored = plan.from_dict(plan.to_dict(original))

    assert restored == original
    assert restored.invocations[0].arguments == {"path": "$paths.input", "label": "pressure"}
    assert restored.invocations[1].arguments["data"] == {
        "frames": ["$fragments.pump.read", None],
        "limit": "$params.limit",
    }
    assert restored.invocations[0].returns == "$fragments.pump.read"
    assert restored.datasets == {"pump": "$dataset.pump.merge"}
    assert plan.ExecutionPlan is models.ExecutionPlan


def test_round_trips_plan_file(tmp_path: pathlib.Path) -> None:
    original = plan.from_dict(_payload())
    target = tmp_path / "plan.json"

    plan.export_json(original, target)

    assert plan.from_json(target) == original


def test_compiler_emits_empty_plan() -> None:
    compiled = compiler.Compiler().compile(spec.Spec())
    assert compiled.plan_version == plan.PLAN_VERSION
    assert compiled.datasets == {}


def test_compiler_names_datasets_fragments_and_each_merge() -> None:
    definition = spec.Spec(
        functions={
            "read": spec_model.FunctionTemplate(
                id="read",
                returns="dataframe",
                entrypoint="support.functions:read_observation_totals",
            ),
            "calculate": spec_model.FunctionTemplate(
                id="calculate",
                returns="dataframe",
                entrypoint="support.functions:sum_observation_features",
                args={"dataset": spec_model.Argument(id="dataset", type="dataframe")},
            ),
        },
        profiles={
            "pump": spec_model.Profile(
                id="pump",
                seed="read",
                features={
                    name: spec_model.Feature(id=name) for name in ("input_1", "first", "second")
                },
                assembly={
                    "read": spec_model.Operator(
                        id="read",
                        compute=spec_model.Binding(function="read"),
                        interface=spec_model.Interface(outputs=["$features.input_1"]),
                    ),
                    **{
                        name: spec_model.Operator(
                            id=name,
                            compute=spec_model.Binding(
                                function="calculate", args={"dataset": "$profiles.@.dataset"}
                            ),
                            merge=spec_model.Binding(
                                function="merge_by_grain",
                                args={
                                    "dataset": "$profiles.@.dataset",
                                    "fragment": "$operators.@.fragment",
                                    "dataset_identifiers": "$profiles.@.grain.ids",
                                },
                            ),
                            interface=spec_model.Interface(
                                inputs=[f"$features.{input_feature}"],
                                outputs=[f"$features.{name}"],
                            ),
                        )
                        for name, input_feature in (("first", "input_1"), ("second", "first"))
                    },
                },
            )
        },
    )

    compiled = compiler.Compiler().compile(definition, validate_spec=False)
    calls = {
        (item.semantics.operator_id, item.semantics.role): item
        for item in compiled.invocations
        if item.semantics is not None
    }
    assert calls["read", "compute"].returns == "$datasets.pump.read"
    assert calls["first", "compute"].returns == "$fragments.pump.first"
    assert calls["first", "merge"].returns == "$dataset.pump.first"
    assert calls["second", "compute"].returns == "$fragments.pump.second"
    assert calls["second", "merge"].returns == "$dataset.pump.second"
    assert calls["first", "merge"].arguments["fragment"] == "$fragments.pump.first"
    assert calls["first", "merge"].arguments["dataset"] == "$datasets.pump.read"
    assert calls["second", "compute"].arguments["dataset"] == "$dataset.pump.first"
    assert calls["second", "merge"].arguments["dataset"] == "$dataset.pump.first"
    assert compiled.datasets == {"pump": "$dataset.pump.second"}
    assert plan.from_dict(plan.to_dict(compiled)) == compiled


@pytest.mark.parametrize(
    "version", [plan.PLAN_VERSION + 1, float(plan.PLAN_VERSION), str(plan.PLAN_VERSION), True, None]
)
def test_requires_exact_integer_version(version: object) -> None:
    payload = _payload()
    payload["plan_version"] = version

    with pytest.raises(ValueError, match="Unsupported plan version"):
        plan.from_dict(payload)


def test_requires_unique_return_names() -> None:
    payload = _payload()
    payload["invocations"][1]["returns"] = "$fragments.pump.read"

    with pytest.raises(ValueError, match="Return name is assigned more than once"):
        plan.from_dict(payload)


@pytest.mark.parametrize("stages", [[["merge", "read"], ["write"]], [["merge"], ["read", "write"]]])
def test_requires_return_producer_before_consumer(stages: list[list[str]]) -> None:
    payload = _payload()
    payload["stages"] = stages

    with pytest.raises(
        ValueError, match=r"Return \$fragments\.pump\.read must be produced before merge"
    ):
        plan.from_dict(payload)


def test_respects_order_within_a_stage() -> None:
    payload = _payload()
    payload["stages"] = [["read", "merge", "write"]]

    assert [item.id for item in plan.from_dict(payload).execution_invocations] == [
        "read",
        "merge",
        "write",
    ]


def test_finds_only_explicit_input_producers() -> None:
    payload = _payload()
    payload["invocations"][1]["arguments"]["data"]["frames"].append("$fragments.pump.read")
    payload["stages"] = [["read", "merge", "write"]]
    original = plan.from_dict(payload)
    serialized = plan.to_dict(original)

    assert original.invocations[1].referenced_results == ("$fragments.pump.read",)
    assert original.input_invocations == {"read": [], "merge": ["read"], "write": ["merge"]}
    assert plan.to_dict(original) == serialized


def test_checks_nested_return_references_and_dataset_aliases() -> None:
    payload = _payload()
    frames = payload["invocations"][1]["arguments"]["data"]["frames"]
    frames[0] = "$fragments.pump.missing"
    with pytest.raises(ValueError, match="Unknown return reference"):
        plan.from_dict(payload)

    payload = _payload()
    payload["datasets"]["pump"] = "$dataset.pump.missing"
    with pytest.raises(ValueError, match="references unknown return"):
        plan.from_dict(payload)


def test_checks_schedule() -> None:
    payload = _payload()
    payload["stages"].append(["write"])
    with pytest.raises(ValueError, match="staged more than once"):
        plan.from_dict(payload)


@pytest.mark.parametrize("reference", ["read_result", "$datasets", "$dataset.pump", "$paths.input"])
@pytest.mark.parametrize("target", ["returns", "dataset"])
def test_requires_qualified_return_bindings(reference: str, target: str) -> None:
    payload = _payload()
    if target == "returns":
        payload["invocations"][0]["returns"] = reference
    else:
        payload["datasets"]["pump"] = reference

    with pytest.raises(ValueError, match="Malformed result reference"):
        plan.from_dict(payload)


@pytest.mark.parametrize(
    "reference",
    ["$datasets", "$fragments.pump.", "$dataset.pump", "$paths", "$paths.", "$params.1"],
)
def test_rejects_malformed_runtime_references(reference: str) -> None:
    payload = _payload()
    payload["invocations"][0]["arguments"]["label"] = {"nested": [reference]}

    with pytest.raises(ValueError, match="Malformed"):
        plan.from_dict(payload)


def test_preserves_literal_json_values() -> None:
    payload = _payload()
    literal = {"kind": "return", "name": "missing", "values": [1, None, False]}
    payload["invocations"][0]["arguments"]["label"] = literal
    invocation = plan.from_dict(copy.deepcopy(payload)).invocations[0]

    assert invocation.arguments["label"] == literal
