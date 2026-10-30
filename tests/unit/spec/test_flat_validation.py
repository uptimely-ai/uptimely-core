"""Contract tests for spec-in atomic rules and their dependency runner."""

from __future__ import annotations

import collections.abc
import graphlib
import inspect
import pathlib
import typing

import pytest

from uptimely import row_context as row_context_model
from uptimely.spec import api, functions, model
from uptimely.spec.validation import spec as validation
from uptimely.spec.validation.rules import actions as action_rules
from uptimely.spec.validation.rules import (
    bindings,
    dimensions,
    entities,
    features,
    row_context,
)
from uptimely.spec.validation.rules import (
    datasets as dataset,
)
from uptimely.spec.validation.rules import functions as function_rules
from uptimely.spec.validation.rules.actions import contracts as action_contracts
from uptimely.spec.validation.rules.actions import dependencies
from uptimely.spec.validation.rules.actions import inputs as action_inputs
from uptimely.spec.validation.rules.actions import outputs as action_outputs

type Mutation = collections.abc.Callable[[model.Spec], object]


def make_spec(kind: functions.FunctionKindId = "vectorize") -> model.Spec:
    """Build a valid document without invoking semantic validation."""
    source_dimensions = ["machine"] if kind == "expand" else ["machine", "time"]
    target_dimensions = ["machine"] if kind == "collapse" else ["machine", "time"]
    args = {} if kind in {"read", "escape"} else {"data": {"type": "dataframe"}}
    input_dataset = "source" if kind in {"collapse", "conform", "expand"} else "target"
    binding_args = (
        {} if kind in {"read", "escape"} else {"data": f"$datasets.{input_dataset}.dataframe"}
    )
    inputs = (
        []
        if kind == "read"
        else ["$features.s"]
        if kind in {"collapse", "conform", "expand", "escape"}
        else ["$features.x"]
    )
    document: dict[str, typing.Any] = {
        "dimensions": {"machine": {"type": "integer"}, "time": {"type": "datetime"}},
        "functions": {
            "read": {
                "kind": "read",
                "returns": "dataframe",
                "entrypoint": "not_imported:read",
            },
            "compute": {
                "kind": kind,
                "returns": functions.FUNCTION_KINDS[kind].returns,
                "entrypoint": "not_imported:compute",
                "args": args,
            },
        },
        "entities": {
            "source_entity": {
                "name": "Source",
                "dimensions": source_dimensions,
                "datasets": {
                    "source": {
                        "features": {"s": {}},
                        "order": [{"dimension": "$dimensions.machine", "direction": "asc"}],
                        "actions": {
                            "read_source": {
                                "binding": {"function": "read"},
                                "features": {"outputs": ["$features.s"]},
                            }
                        },
                    }
                },
            },
            "target_entity": {
                "name": "Target",
                "dimensions": target_dimensions,
                "datasets": {
                    "target": {
                        "features": (
                            {"x": {}} if kind in {"write", "escape"} else {"x": {}, "y": {}}
                        ),
                        "order": [{"dimension": "$dimensions.machine", "direction": "asc"}],
                        "actions": {
                            "read_base": {
                                "binding": {"function": "read"},
                                "features": {"outputs": ["$features.x"]},
                            },
                            "compute": {
                                "binding": {"function": "compute", "args": binding_args},
                                "features": {
                                    "inputs": inputs,
                                    "outputs": (
                                        [] if kind in {"write", "escape"} else ["$features.y"]
                                    ),
                                },
                            },
                        },
                    }
                },
            },
        },
    }
    return model.Spec.model_validate(document)


def target(spec: model.Spec) -> model.Dataset:
    return spec.entities["target_entity"].datasets["target"]


def compute(spec: model.Spec) -> model.Action:
    return target(spec).actions["compute"]


@pytest.mark.parametrize(
    "validate",
    validation.VALIDATION_DEPENDENCIES,
    ids=lambda validate: f"{validate.__module__.rsplit('.', 1)[-1]}.{validate.__name__}",
)
def test_atomic_rules_accept_spec_and_do_not_mutate(
    validate: validation.Validator,
) -> None:
    spec = make_spec()
    before = spec.model_dump()
    assert validate(spec) is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
def test_full_validation_preserves_valid_function_kinds(kind: functions.FunctionKindId) -> None:
    spec = make_spec(kind)
    before = spec.model_dump()
    assert validation.validate_spec(spec) is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
def test_source_discovery_visits_every_action_kind(kind: functions.FunctionKindId) -> None:
    spec = make_spec(kind)
    before = spec.model_dump()
    sources = tuple(action_inputs.iter_input_sources(spec))
    assert [item.action.action for item in sources] == [
        item.action for item in action_rules.iter_actions(spec)
    ]
    item = next(item for item in sources if item.action.action is compute(spec))
    if kind == functions.READ:
        assert item.candidates == ()
        assert item.source is None
    else:
        expected = "target" if kind in {functions.VECTORIZE, functions.WRITE} else "source"
        assert item.source is not None
        assert item.source.dataset.id == expected
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
@pytest.mark.parametrize(
    "inputs",
    [[], ["machine"], ["missing"], ["s", "x"], ["s", "missing"]],
)
def test_source_discovery_preserves_unresolved_inputs_for_every_kind(
    kind: functions.FunctionKindId, inputs: list[str]
) -> None:
    spec = make_spec(kind)
    compute(spec).features.inputs = [f"$features.{feature}" for feature in inputs]
    before = spec.model_dump()
    item = next(
        item
        for item in action_inputs.iter_input_sources(spec)
        if item.action.action is compute(spec)
    )
    assert [feature for feature, _ in item.candidates] == [
        feature for feature in inputs if feature not in spec.dimensions
    ]
    assert item.source is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
def test_source_discovery_does_not_choose_an_ambiguous_owner(
    kind: functions.FunctionKindId,
) -> None:
    spec = make_spec(kind)
    source_entity = spec.entities["source_entity"]
    duplicate = source_entity.datasets["source"].model_copy(deep=True)
    duplicate.id = "duplicate"
    source_entity.datasets["duplicate"] = duplicate
    compute(spec).features.inputs = ["$features.s"]
    item = next(
        item
        for item in action_inputs.iter_input_sources(spec)
        if item.action.action is compute(spec)
    )
    assert [owner.dataset.id for _, owners in item.candidates for owner in owners] == [
        "source",
        "duplicate",
    ]
    assert item.source is None


def test_every_rule_is_registered_with_one_spec_parameter() -> None:
    modules = (
        action_contracts,
        action_inputs,
        action_outputs,
        bindings,
        dataset,
        dependencies,
        dimensions,
        entities,
        features,
        function_rules,
        row_context,
    )
    rules = {
        function
        for module in modules
        for name, function in inspect.getmembers(module, inspect.isfunction)
        if name.startswith("validate_")
    }
    assert rules == validation.VALIDATION_DEPENDENCIES.keys()
    for validate in rules:
        assert list(inspect.signature(validate).parameters) == ["spec"]
    for prerequisites in validation.VALIDATION_DEPENDENCIES.values():
        assert set(prerequisites) <= rules


def test_runner_orders_dependencies_and_runs_shared_prerequisites_once(
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
        "VALIDATION_DEPENDENCIES",
        {third: (first, second), second: (first,), first: ()},
    )
    validation.validate_spec(spec)
    assert seen == ["first", "second", "third"]


def test_failed_prerequisite_stops_runner_and_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []

    def first(spec: model.Spec) -> None:
        seen.append("first")
        raise ValueError("invalid prerequisite")

    def dependent(spec: model.Spec) -> None:
        pytest.fail("A dependent validator must not run")

    def warn(spec: model.Spec) -> None:
        pytest.fail("Warnings must not be emitted for invalid specs")

    monkeypatch.setattr(validation, "VALIDATION_DEPENDENCIES", {dependent: (first,), first: ()})
    monkeypatch.setattr(action_outputs, "warn_unproduced_features", warn)
    with pytest.raises(ValueError, match="invalid prerequisite"):
        validation.validate_spec(make_spec())
    assert seen == ["first"]


def test_dependency_configuration_cycle_fails_before_running_rules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def independent(spec: model.Spec) -> None:
        pytest.fail("Invalid configuration must fail before any rule runs")

    def cyclic(spec: model.Spec) -> None:
        pytest.fail("Cyclic rule must not run")

    monkeypatch.setattr(validation, "VALIDATION_DEPENDENCIES", {independent: (), cyclic: (cyclic,)})
    with pytest.raises(graphlib.CycleError):
        validation.validate_spec(make_spec())


@pytest.mark.parametrize(
    ("validate", "kind", "mutate", "message"),
    [
        (
            dimensions.validate_parent,
            "read",
            lambda s: setattr(s.dimensions["machine"], "parent", "missing"),
            "unknown parent",
        ),
        (
            dimensions.validate_parent_cycle,
            "read",
            lambda s: setattr(s.dimensions["machine"], "parent", "machine"),
            "parent cycle",
        ),
        (
            entities.validate_entity_dimensions,
            "read",
            lambda s: setattr(s.entities["target_entity"].dimensions[0], "id", "missing"),
            "unknown dimensions",
        ),
        (
            dataset.validate_dataset_ids,
            "read",
            lambda s: setattr(target(s), "id", "source"),
            "Duplicate dataset",
        ),
        (
            dataset.validate_order_dimension,
            "read",
            lambda s: setattr(target(s).order[0], "dimension", "$dimensions.missing"),
            "order references",
        ),
        (
            dataset.validate_unique_order_dimension,
            "read",
            lambda s: target(s).order.append(target(s).order[0]),
            "repeats dimension",
        ),
        (
            function_rules.validate_return_kind,
            "vectorize",
            lambda s: setattr(s.functions["compute"], "returns", "none"),
            "must declare returns",
        ),
        (
            function_rules.validate_dataframe_count,
            "vectorize",
            lambda s: s.functions["compute"].args.clear(),
            "requires 1 dataframe",
        ),
        (
            action_outputs.validate_function_reference,
            "vectorize",
            lambda s: setattr(compute(s).binding, "function", "missing"),
            "unknown functions",
        ),
        (
            action_outputs.validate_function_id,
            "vectorize",
            lambda s: setattr(s.functions["compute"], "id", " "),
            "non-empty string id",
        ),
        (
            action_outputs.validate_output_names,
            "vectorize",
            lambda s: setattr(compute(s).features, "outputs", ["$features. "]),
            "non-empty output",
        ),
        (
            action_outputs.validate_output_presence,
            "vectorize",
            lambda s: compute(s).features.outputs.clear(),
            "one or more features",
        ),
        (
            action_outputs.validate_nonproducing_outputs,
            "write",
            lambda s: compute(s).features.outputs.append("$features.x"),
            "cannot produce features",
        ),
        (
            features.validate_feature_ownership,
            "vectorize",
            lambda s: target(s).features.update({"s": model.Feature(id="s")}),
            "Duplicate feature",
        ),
        (
            action_outputs.validate_dimension_collision,
            "vectorize",
            lambda s: compute(s).features.outputs.append("$features.machine"),
            "duplicate entity",
        ),
        (
            action_outputs.validate_output_feature,
            "vectorize",
            lambda s: compute(s).features.outputs.append("$features.missing"),
            "unknown feature",
        ),
        (
            action_outputs.validate_unique_producer,
            "vectorize",
            lambda s: compute(s).features.outputs.append("$features.x"),
            "multiple actions",
        ),
        (
            action_outputs.validate_collapse_output,
            "collapse",
            lambda s: setattr(compute(s).features, "outputs", ["$features.machine"]),
            "non-dimension feature",
        ),
        (
            action_outputs.validate_current_feature_selector,
            "vectorize",
            lambda s: (
                compute(s).features.outputs.append("$features.x"),
                compute(s).binding.args.update({"output": "$features.@.id"}),
            ),
            "cannot use",
        ),
        (
            action_inputs.validate_input_feature,
            "vectorize",
            lambda s: compute(s).features.inputs.append("$features.missing"),
            "unknown input",
        ),
        (
            action_inputs.validate_input_scope,
            "vectorize",
            lambda s: compute(s).features.inputs.append("$features.s"),
            "another dataset",
        ),
        (
            action_inputs.validate_feature_reference,
            "vectorize",
            lambda s: compute(s).binding.args.update(
                {"extra": {"nested": ["$features.missing.id"]}}
            ),
            "unknown feature",
        ),
        (
            action_inputs.validate_dataset_reference,
            "vectorize",
            lambda s: compute(s).binding.args.update({"data": "$datasets.missing.dataframe"}),
            "unknown dataset",
        ),
        (
            action_inputs.validate_dimension_reference,
            "vectorize",
            lambda s: compute(s).binding.args.update({"extra": ["$dimensions.missing.id"]}),
            "unknown dimension",
        ),
        (
            bindings.validate_arguments,
            "vectorize",
            lambda s: compute(s).binding.args.clear(),
            "missing arguments",
        ),
        (
            bindings.validate_selector_type,
            "vectorize",
            lambda s: compute(s).binding.args.update({"data": "$datasets.target.id"}),
            "requires argument type",
        ),
        (
            action_inputs.validate_source_feature,
            "collapse",
            lambda s: compute(s).features.inputs.clear(),
            "must reference a source feature",
        ),
        (
            action_inputs.validate_feature_owner,
            "collapse",
            lambda s: compute(s).features.inputs.append("$features.missing"),
            "unknown input",
        ),
        (
            action_inputs.validate_source_count,
            "collapse",
            lambda s: compute(s).features.inputs.append("$features.x"),
            "belong to one dataset",
        ),
        (
            action_inputs.validate_source_target,
            "collapse",
            lambda s: setattr(compute(s).features, "inputs", ["$features.x"]),
            "target dataset",
        ),
        (
            action_inputs.validate_grouping_dimensions,
            "collapse",
            lambda s: s.entities["source_entity"].dimensions.clear(),
            "grouping dimensions",
        ),
        (
            action_inputs.validate_source_features,
            "collapse",
            lambda s: (
                s.dimensions.update({"other": model.Dimension(id="other", type="integer")}),
                compute(s).features.inputs.append("$features.other"),
            ),
            "outside source",
        ),
        (
            action_inputs.validate_source_dimensions,
            "collapse",
            lambda s: (
                s.dimensions.update({"other": model.Dimension(id="other", type="integer")}),
                compute(s).binding.args.update({"extra": "$dimensions.other.id"}),
            ),
            "unknown source dimensions",
        ),
        (
            action_contracts.validate_dataframe_reference,
            "vectorize",
            lambda s: compute(s).binding.args.update({"data": 42}),
            "must reference a dataset",
        ),
        (
            action_contracts.validate_dataframe_selector,
            "vectorize",
            lambda s: compute(s).binding.args.update({"data": "$datasets.target.id"}),
            "must reference a dataframe",
        ),
        (
            action_contracts.validate_dataframe_source,
            "vectorize",
            lambda s: compute(s).binding.args.update({"data": "$datasets.missing.dataframe"}),
            "unknown dataset",
        ),
        (
            action_contracts.validate_dataset_count,
            "collapse",
            lambda s: s.functions["compute"].args.clear(),
            "exactly 1 foreign",
        ),
        (
            action_contracts.validate_foreign_dataframe,
            "collapse",
            lambda s: compute(s).binding.args.update({"data": "$datasets.target.dataframe"}),
            "foreign source",
        ),
        (
            action_contracts.validate_input_feature_source_count,
            "conform",
            lambda s: compute(s).features.inputs.append("$features.x"),
            "one source dataset",
        ),
        (
            action_contracts.validate_dataframe_feature_source,
            "conform",
            lambda s: compute(s).binding.args.update({"data": "$datasets.target.dataframe"}),
            "foreign source dataset source",
        ),
        (
            action_contracts.validate_dataframe_features,
            "expand",
            lambda s: compute(s).features.inputs.append("$features.time"),
            "dataframe inputs",
        ),
        (
            action_contracts.validate_feature_input_scope,
            "read",
            lambda s: compute(s).features.inputs.append("$features.x"),
            "cannot declare",
        ),
        (
            action_contracts.validate_target_input,
            "vectorize",
            lambda s: compute(s).binding.args.update({"data": "$datasets.source.dataframe"}),
            "consume its target",
        ),
        (
            action_contracts.validate_write_dataframe,
            "write",
            lambda s: compute(s).binding.args.update({"data": "$datasets.source.dataframe"}),
            "publish a foreign",
        ),
        (
            action_contracts.validate_collapse_source,
            "collapse",
            lambda s: compute(s).binding.args.update({"data": "$datasets.target.dataframe"}),
            "consume its source",
        ),
        (
            action_contracts.validate_collapse_dimensions,
            "collapse",
            lambda s: s.entities["target_entity"].dimensions.append(s.dimensions["time"]),
            "strictly higher",
        ),
        (
            action_contracts.validate_conform_dimensions,
            "conform",
            lambda s: s.entities["target_entity"].dimensions.pop(),
            "preserve target",
        ),
        (
            action_contracts.validate_expand_dimensions,
            "expand",
            lambda s: s.entities["source_entity"].dimensions.append(s.dimensions["time"]),
            "lower-dimensional",
        ),
        (
            action_contracts.validate_matching_keys,
            "expand",
            lambda s: compute(s).binding.args.update({"keys": "$datasets.target.dimensions.ids"}),
            "Matching key",
        ),
        (
            dependencies.validate_action_cycle,
            "vectorize",
            lambda s: compute(s).features.inputs.append("$features.y"),
            "dependency cycle",
        ),
    ],
    ids=lambda value: value.__name__ if callable(value) else str(value),
)
def test_atomic_rules_reject_their_own_invariant(
    validate: validation.Validator,
    kind: functions.FunctionKindId,
    mutate: Mutation,
    message: str,
) -> None:
    spec = make_spec(kind)
    mutate(spec)
    before = spec.model_dump()
    with pytest.raises(ValueError, match=message):
        validate(spec)
    with pytest.raises(ValueError):
        validation.validate_spec(spec)
    assert spec.model_dump() == before


@pytest.mark.parametrize(
    ("validate", "dimension", "before", "message"),
    [
        (row_context.validate_dataset_order, None, {"rows": 1}, "requires dataset order"),
        (row_context.validate_dimension, "$dimensions.missing", {"steps": 1}, "input entity"),
        (
            row_context.validate_dimension_type,
            "$dimensions.machine",
            {"time": "1s"},
            "must have type datetime",
        ),
        (
            row_context.validate_dimension_order,
            "$dimensions.time",
            {"time": "1s"},
            "must occur in dataset order",
        ),
    ],
)
def test_row_context_rules(
    validate: validation.Validator,
    dimension: str | None,
    before: dict[str, int | str],
    message: str,
) -> None:
    spec = make_spec()
    compute(spec).row_context = row_context_model.RowContext.model_validate(
        {"dimension": dimension, "before": before}
    )
    if validate is row_context.validate_dataset_order:
        target(spec).order.clear()
    with pytest.raises(ValueError, match=message):
        validate(spec)


def test_reference_failure_blocks_cycle_check() -> None:
    spec = make_spec()
    spec.dimensions["machine"].parent = "missing"
    with pytest.raises(ValueError, match="unknown parent: missing"):
        validation.validate_spec(spec)


def test_cycle_uses_action_dictionary_keys_after_model_id_edit() -> None:
    spec = make_spec()
    compute(spec).id = "edited_model_id"
    compute(spec).features.inputs.append("$features.y")
    with pytest.raises(ValueError, match="dependency cycle: target.compute"):
        validation.validate_spec(spec)


def test_revalidation_observes_edits_and_warns_only_after_success() -> None:
    spec = make_spec()
    validation.validate_spec(spec)
    target(spec).features["unproduced"] = model.Feature(id="unproduced")
    with pytest.warns(UserWarning, match="Features have no producer action: unproduced"):
        validation.validate_spec(spec)
    compute(spec).features.inputs.append("$features.missing")
    with pytest.raises(ValueError, match="unknown input feature: missing"):
        validation.validate_spec(spec)


def test_load_spec_still_validates(tmp_path: pathlib.Path) -> None:
    spec = make_spec()
    path = tmp_path / "spec.json"
    path.write_text(spec.model_dump_json())
    assert api.load_spec(path) == spec
    compute(spec).features.inputs.append("$features.missing")
    path.write_text(spec.model_dump_json())
    with pytest.raises(ValueError, match="unknown input feature: missing"):
        api.load_spec(path)
