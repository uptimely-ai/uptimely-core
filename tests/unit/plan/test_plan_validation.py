import copy

import pytest

from uptimely import plan


def _payload() -> dict[str, object]:
    return {
        "plan_version": plan.PLAN_VERSION,
        "required_backend": "polars",
        "invocations": [
            {
                "id": "read",
                "entrypoint": "example:read",
                "arguments": {},
                "returns": "$datasets.pump.read",
            },
            {
                "id": "compute",
                "entrypoint": "example:compute",
                "arguments": {"dataset": "$datasets.pump.read"},
                "returns": "$dataset.pump.result",
            },
        ],
        "stages": [["read"], ["compute"]],
        "datasets": {"pump": "$dataset.pump.result"},
    }


def test_plan_requires_dataset_aliases() -> None:
    payload = _payload()
    del payload["datasets"]

    with pytest.raises(ValueError, match="datasets"):
        plan.from_dict(payload)


def test_plan_rejects_unknown_fields() -> None:
    payload = _payload()
    payload["spec_version"] = 1

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        plan.from_dict(payload)


def test_plan_rejects_unknown_stage_invocations() -> None:
    payload = _payload()
    payload["stages"] = [["read"], ["missing"]]

    with pytest.raises(ValueError, match="Stage references unknown invocation: missing"):
        plan.from_dict(payload)


def test_plan_rejects_duplicate_and_unstaged_invocations() -> None:
    duplicate_payload = _payload()
    duplicate_payload["invocations"].append(copy.deepcopy(duplicate_payload["invocations"][0]))

    with pytest.raises(ValueError, match="duplicate invocation IDs"):
        plan.from_dict(duplicate_payload)

    unstaged_payload = _payload()
    unstaged_payload["stages"] = [["read"]]

    with pytest.raises(ValueError, match="stage every invocation exactly once"):
        plan.from_dict(unstaged_payload)


def test_plan_rejects_references_to_unavailable_results() -> None:
    payload = _payload()
    payload["invocations"][1]["arguments"]["dataset"] = "$datasets.pump.missing"

    with pytest.raises(ValueError, match="Unknown return reference"):
        plan.from_dict(payload)

    payload = _payload()
    payload["datasets"]["pump"] = "$dataset.pump.missing"

    with pytest.raises(ValueError, match="references unknown return"):
        plan.from_dict(payload)


def test_plan_rejects_consumers_scheduled_before_their_results() -> None:
    payload = _payload()
    payload["stages"] = [["compute"], ["read"]]

    with pytest.raises(ValueError, match="must be produced before compute"):
        plan.from_dict(payload)


def test_plan_requires_explicit_invocation_arguments_and_returns() -> None:
    payload = _payload()
    del payload["invocations"][0]["arguments"]

    with pytest.raises(ValueError, match="arguments"):
        plan.from_dict(payload)

    payload = _payload()
    del payload["invocations"][0]["returns"]

    with pytest.raises(ValueError, match="returns"):
        plan.from_dict(payload)


def test_invocation_result_contracts_are_validated() -> None:
    with pytest.raises(ValueError, match="Merge invocations must have result='target'"):
        plan.InvocationSemantics(
            role="merge",
            result="none",
            function_id="merge",
            operator_id="merge",
            profile_id="pump",
        )
