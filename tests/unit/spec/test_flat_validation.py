"""Contract tests for spec-in atomic rules and their dependency runner."""

from __future__ import annotations

import collections.abc
import dataclasses
import graphlib
import inspect
import json
import pathlib
import types
import typing

import pydantic
import pytest

from uptimely import row_context as row_context_model
from uptimely.spec import api, functions, model
from uptimely.spec.python import actions as assembly
from uptimely.spec.python import feature as python_feature
from uptimely.spec.python import profile as python_profile
from uptimely.spec.python import ref as python_ref
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
from uptimely.spec.validation.rules.actions import contracts as action_contracts
from uptimely.spec.validation.rules.actions import dependencies
from uptimely.spec.validation.rules.actions import inputs as action_inputs
from uptimely.spec.validation.rules.actions import outputs as action_outputs

type Mutation = collections.abc.Callable[[model.Spec], object]


def make_spec(kind: functions.FunctionKindId = "vectorize") -> model.Spec:
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
        {} if kind in {"read", "escape"} else {"data": f"$profiles.{input_dataset}.dataframe"}
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
                                "$features.machine",
                                *(["$features.time"] if len(source_grain) > 1 else []),
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
                                "$features.machine",
                                *(["$features.time"] if len(target_grain) > 1 else []),
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


def test_dimension_change_uses_dimension_identities_not_cardinality(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec = make_spec("conform")
    spec.dimensions["other"] = model.Dimension(
        id="other",
        resolutions={"other": model.Resolution(id="other", key="other", type="integer")},
    )
    spec.profiles["source"].grain[1] = model.Grain(dimension="other", resolution="other")
    assert len(spec.profiles["source"].dimension_ids) == len(spec.profiles["target"].dimension_ids)

    with pytest.raises(ValueError, match="preserve target dimensionality"):
        action_contracts.validate_dimension_change(spec)

    definitions = dict(functions.FUNCTION_KINDS)
    definitions[functions.CONFORM] = dataclasses.replace(
        definitions[functions.CONFORM], dimension_change="unrestricted"
    )
    monkeypatch.setattr(functions, "FUNCTION_KINDS", types.MappingProxyType(definitions))

    assert action_contracts.validate_dimension_change(spec) is None


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
    sources = spec.input_sources
    assert list(sources) == [key for key, _ in spec.operator_items]
    key = ("target", "compute")
    source = sources[key]
    if kind == functions.READ:
        assert spec.input_candidates[key] == ()
        assert source is None
    else:
        expected = "target" if kind in {functions.VECTORIZE, functions.WRITE} else "source"
        assert source is not None
        assert source == expected
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
    compute(spec).interface.inputs = [f"$features.{feature}" for feature in inputs]
    before = spec.model_dump()
    key = ("target", "compute")
    assert [feature for feature, _ in spec.input_candidates[key]] == [
        feature for feature in inputs if feature not in spec.grain_key_ids
    ]
    assert spec.input_sources[key] is None
    assert spec.model_dump() == before


@pytest.mark.parametrize("kind", functions.FUNCTION_KINDS)
def test_source_discovery_does_not_choose_an_ambiguous_owner(
    kind: functions.FunctionKindId,
) -> None:
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


def test_every_rule_is_registered_with_one_spec_parameter() -> None:
    modules = (
        action_contracts,
        action_inputs,
        action_outputs,
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
            lambda s: setattr(s.dimensions["machine"].resolutions["machine"], "parent", "missing"),
            "unknown parent",
        ),
        (
            dimensions.validate_parent_cycle,
            "read",
            lambda s: setattr(s.dimensions["machine"].resolutions["machine"], "parent", "machine"),
            "parent cycle",
        ),
        (
            profile_identity.validate_profile_ids,
            "read",
            lambda s: setattr(target(s), "id", "source"),
            "Profile key",
        ),
        (
            profile_identity.validate_order_dimension,
            "read",
            lambda s: setattr(target(s).order[0], "dimension", "$dimensions.missing"),
            "order references",
        ),
        (
            profile_identity.validate_unique_order_dimension,
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
            lambda s: setattr(compute(s).compute, "function", "missing"),
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
            lambda s: setattr(compute(s).interface, "outputs", ["$features. "]),
            "non-empty output",
        ),
        (
            action_outputs.validate_output_presence,
            "vectorize",
            lambda s: compute(s).interface.outputs.clear(),
            "one or more features",
        ),
        (
            action_outputs.validate_nonproducing_outputs,
            "write",
            lambda s: compute(s).interface.outputs.append("$features.x"),
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
            lambda s: compute(s).interface.outputs.append("$features.machine"),
            "duplicate profile",
        ),
        (
            action_outputs.validate_output_feature,
            "vectorize",
            lambda s: compute(s).interface.outputs.append("$features.missing"),
            "unknown feature",
        ),
        (
            action_outputs.validate_unique_producer,
            "vectorize",
            lambda s: compute(s).interface.outputs.append("$features.x"),
            "multiple actions",
        ),
        (
            action_outputs.validate_collapse_output,
            "collapse",
            lambda s: setattr(compute(s).interface, "outputs", ["$features.machine"]),
            "non-dimension feature",
        ),
        (
            action_outputs.validate_current_feature_selector,
            "vectorize",
            lambda s: (
                compute(s).interface.outputs.append("$features.x"),
                compute(s).compute.args.update({"output": "$features.@.id"}),
            ),
            "cannot use",
        ),
        (
            action_inputs.validate_input_feature,
            "vectorize",
            lambda s: compute(s).interface.inputs.append("$features.missing"),
            "unknown input",
        ),
        (
            action_inputs.validate_input_scope,
            "vectorize",
            lambda s: compute(s).interface.inputs.append("$features.s"),
            "another profile",
        ),
        (
            action_inputs.validate_feature_reference,
            "vectorize",
            lambda s: compute(s).compute.args.update(
                {"extra": {"nested": ["$features.missing.id"]}}
            ),
            "unknown feature",
        ),
        (
            action_inputs.validate_dataset_reference,
            "vectorize",
            lambda s: compute(s).compute.args.update({"data": "$profiles.missing.dataframe"}),
            "unknown profile",
        ),
        (
            action_inputs.validate_dimension_reference,
            "vectorize",
            lambda s: compute(s).compute.args.update({"extra": ["$dimensions.missing.id"]}),
            "unknown dimension",
        ),
        (
            bindings.validate_arguments,
            "vectorize",
            lambda s: compute(s).compute.args.clear(),
            "missing arguments",
        ),
        (
            bindings.validate_selector_type,
            "vectorize",
            lambda s: compute(s).compute.args.update({"data": "$profiles.target.id"}),
            "requires argument type",
        ),
        (
            action_inputs.validate_source_feature,
            "collapse",
            lambda s: compute(s).interface.inputs.clear(),
            "must reference a source feature",
        ),
        (
            action_inputs.validate_feature_owner,
            "collapse",
            lambda s: compute(s).interface.inputs.append("$features.missing"),
            "unknown input",
        ),
        (
            action_inputs.validate_source_count,
            "collapse",
            lambda s: compute(s).interface.inputs.append("$features.x"),
            "belong to one profile",
        ),
        (
            action_inputs.validate_source_target,
            "collapse",
            lambda s: setattr(compute(s).interface, "inputs", ["$features.x"]),
            "target profile",
        ),
        (
            action_inputs.validate_grouping_dimensions,
            "collapse",
            lambda s: s.profiles["source"].grain.clear(),
            "grouping keys",
        ),
        (
            action_inputs.validate_source_features,
            "collapse",
            lambda s: (
                s.profiles["target"].features.update({"other": model.Feature(id="other")}),
                compute(s).interface.inputs.append("$features.other"),
                s.input_sources.__setitem__(("target", "compute"), "source"),
            ),
            "outside source",
        ),
        (
            action_inputs.validate_source_dimensions,
            "collapse",
            lambda s: (
                s.dimensions.update(
                    {
                        "other": model.Dimension(
                            id="other",
                            resolutions={
                                "other": model.Resolution(id="other", key="other", type="integer")
                            },
                        )
                    }
                ),
                compute(s).compute.args.update({"extra": "$dimensions.other.id"}),
            ),
            "unknown source dimensions",
        ),
        (
            action_contracts.validate_dataset_argument_reference,
            "vectorize",
            lambda s: compute(s).compute.args.update({"data": 42}),
            "must reference a profile",
        ),
        (
            action_contracts.validate_dataset_argument_selector,
            "vectorize",
            lambda s: compute(s).compute.args.update({"data": "$profiles.target.id"}),
            "must select profile data",
        ),
        (
            action_contracts.validate_dataset_argument_source,
            "vectorize",
            lambda s: compute(s).compute.args.update({"data": "$profiles.missing.dataframe"}),
            "unknown profile",
        ),
        (
            action_contracts.validate_dataset_argument_count,
            "collapse",
            lambda s: s.functions["compute"].args.clear(),
            "exactly 1 foreign",
        ),
        (
            action_contracts.validate_foreign_dataset_argument,
            "collapse",
            lambda s: compute(s).compute.args.update({"data": "$profiles.target.dataframe"}),
            "foreign source",
        ),
        (
            action_contracts.validate_input_feature_source_count,
            "conform",
            lambda s: compute(s).interface.inputs.append("$features.x"),
            "one source profile",
        ),
        (
            action_contracts.validate_dataset_argument_feature_source,
            "conform",
            lambda s: compute(s).compute.args.update({"data": "$profiles.target.dataframe"}),
            "foreign source profile source",
        ),
        (
            action_contracts.validate_dataset_argument_features,
            "expand",
            lambda s: compute(s).interface.inputs.append("$features.time"),
            "profile inputs",
        ),
        (
            action_contracts.validate_feature_input_scope,
            "read",
            lambda s: compute(s).interface.inputs.append("$features.x"),
            "cannot declare",
        ),
        (
            action_contracts.validate_target_dataset_input,
            "vectorize",
            lambda s: compute(s).compute.args.update({"data": "$profiles.source.dataframe"}),
            "consume its target",
        ),
        (
            action_contracts.validate_target_dataset_only,
            "write",
            lambda s: compute(s).compute.args.update({"data": "$profiles.source.dataframe"}),
            "publish a foreign",
        ),
        (
            action_contracts.validate_dimension_source,
            "collapse",
            lambda s: compute(s).compute.args.update({"data": "$profiles.target.dataframe"}),
            "consume its source",
        ),
        (
            action_contracts.validate_dimension_change,
            "collapse",
            lambda s: s.profiles["target"].grain.append(
                model.Grain(dimension="time", resolution="time")
            ),
            "strictly higher",
        ),
        (
            action_contracts.validate_dimension_change,
            "conform",
            lambda s: s.profiles["target"].grain.pop(),
            "preserve target",
        ),
        (
            action_contracts.validate_dimension_expansion_input,
            "expand",
            lambda s: s.profiles["source"].grain.append(
                model.Grain(dimension="time", resolution="time")
            ),
            "lower-dimensional",
        ),
        (
            action_contracts.validate_matching_keys,
            "expand",
            lambda s: compute(s).compute.args.update({"keys": "$profiles.target.grain.ids"}),
            "Matching key",
        ),
        (
            dependencies.validate_action_cycle,
            "vectorize",
            lambda s: compute(s).interface.inputs.append("$features.y"),
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
        (row_context.validate_dataset_order, None, {"rows": 1}, "requires profile order"),
        (row_context.validate_dimension, "$dimensions.missing", {"steps": 1}, "input profile"),
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
            "must occur in profile order",
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
    spec.dimensions["machine"].resolutions["machine"].parent = "missing"
    with pytest.raises(ValueError, match="unknown parent resolution: missing"):
        validation.validate_spec(spec)


def test_cycle_uses_action_dictionary_keys_after_model_id_edit() -> None:
    spec = make_spec()
    compute(spec).id = "edited_model_id"
    compute(spec).interface.inputs.append("$features.y")
    with pytest.raises(ValueError, match="dependency cycle: target.compute"):
        validation.validate_spec(spec)


def test_new_model_validation_observes_edits_and_warns_only_after_success() -> None:
    spec = make_spec()
    validation.validate_spec(spec)
    target(spec).features["unproduced"] = model.Feature(id="unproduced")
    spec = model.Spec.model_validate(spec.model_dump())
    with pytest.warns(UserWarning, match="Features have no producer action: unproduced"):
        validation.validate_spec(spec)
    compute(spec).interface.inputs.append("$features.missing")
    spec = model.Spec.model_validate(spec.model_dump())
    with pytest.raises(ValueError, match="unknown input feature: missing"):
        validation.validate_spec(spec)


def test_load_spec_still_validates(tmp_path: pathlib.Path) -> None:
    spec = make_spec()
    path = tmp_path / "spec.json"
    path.write_text(spec.model_dump_json())
    assert api.load_spec(path) == spec
    compute(spec).interface.inputs.append("$features.missing")
    path.write_text(spec.model_dump_json())
    with pytest.raises(ValueError, match="unknown input feature: missing"):
        api.load_spec(path)


@pytest.mark.parametrize("validate", [False, True])
def test_load_spec_can_defer_semantic_validation(tmp_path: pathlib.Path, validate: bool) -> None:
    document = make_spec()
    compute(document).interface.inputs.append("$features.missing")
    path = tmp_path / "spec.json"
    path.write_text(document.model_dump_json())

    if validate:
        with pytest.raises(ValueError, match="unknown input feature: missing"):
            api.load_spec(path, validate=validate)
    else:
        loaded = api.load_spec(path, validate=validate)
        with pytest.raises(ValueError, match="unknown input feature: missing"):
            validation.validate_spec(loaded)


@pytest.mark.parametrize("validate", [False, True])
def test_load_spec_always_checks_document_structure(tmp_path: pathlib.Path, validate: bool) -> None:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"spec_version": True}))

    with pytest.raises(pydantic.ValidationError, match="spec_version"):
        api.load_spec(path, validate=validate)


def _python_profile_with_missing_input() -> python_profile.Profile:
    return python_profile.Profile(
        id="source",
        assembly=[
            assembly.Operator(
                id="compute",
                interface=assembly.Interface(
                    inputs=[python_ref.feature("missing")],
                    outputs=[python_feature.Feature(id="result")],
                ),
                compute=assembly.Binding(
                    function=python_ref.function("external:compute", kind="vectorize"),
                    arguments={"data": python_ref.profile().data},
                ),
            )
        ],
    )


@pytest.mark.parametrize("validate", [False, True])
def test_from_python_can_defer_semantic_validation(validate: bool) -> None:
    profile = _python_profile_with_missing_input()

    if validate:
        with pytest.raises(ValueError, match="unknown input feature: missing"):
            api.from_python(
                profiles=[profile],
                validate=validate,
            )
    else:
        loaded = api.from_python(
            profiles=[profile],
            validate=validate,
        )
        with pytest.raises(ValueError, match="unknown input feature: missing"):
            validation.validate_spec(loaded)


@pytest.mark.parametrize("validate", [False, True])
def test_from_python_always_checks_document_structure(validate: bool) -> None:
    with pytest.raises(pydantic.ValidationError, match="unexpected"):
        api.from_python(
            profiles=[python_profile.Profile(id="source")],
            functions={"invalid": {"unexpected": True}},
            validate=validate,
        )
