import json
import pathlib

import pydantic
import pytest
from support import examples as example_support

from uptimely import spec
from uptimely.spec import model, validation

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


def _write_configuration(tmp_path: pathlib.Path, configuration: dict, name: str) -> pathlib.Path:
    path = tmp_path / name
    path.write_text(json.dumps(configuration), encoding="utf-8")
    return path


def test_spec_rejects_unknown_fields(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["unexpected"] = True

    with pytest.raises(pydantic.ValidationError, match="unexpected"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "unknown.json"))


@pytest.mark.parametrize("old_key", ["actions", "binding", "features"])
def test_spec_rejects_version_four_operator_keys(old_key: str) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry"]
    operator_key = "read_pump_telemetry"
    operator = profile["assembly"][operator_key]
    new_key = {"actions": "assembly", "binding": "compute", "features": "interface"}[old_key]
    if old_key == "actions":
        profile[old_key] = profile.pop(new_key)
    else:
        operator[old_key] = operator.pop(new_key)

    with pytest.raises(pydantic.ValidationError, match="Extra inputs are not permitted"):
        model.Spec.model_validate(configuration)


def test_spec_rejects_explicit_operator_id_attribute() -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["profiles"]["pump_telemetry"]["assembly"]["read_pump_telemetry"]["id"] = (
        "read_pump_telemetry"
    )

    with pytest.raises(ValueError, match="not an 'id' attribute"):
        model.Spec.model_validate(configuration)


def test_spec_accepts_top_level_name(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["name"] = "Pump analytics"

    spec_definition = spec.load_spec(_write_configuration(tmp_path, configuration, "named.json"))

    assert spec_definition.name == "Pump analytics"


def test_loading_keeps_only_declarations_on_the_document() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)

    validation.validate_spec(spec_definition)
    assert not hasattr(spec_definition, "calls")
    assert not hasattr(spec_definition, "path")


def test_canonical_model_rejects_file_loading_arguments() -> None:
    with pytest.raises(pydantic.ValidationError, match="json"):
        spec.Spec.model_validate({"json": str(SPEC_PATH)})


@pytest.mark.parametrize("version", [0, 1, 2, 3, 4, 5, 6, 8, "7", True])
def test_spec_rejects_unsupported_version(tmp_path: pathlib.Path, version: object) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["spec_version"] = version

    with pytest.raises(pydantic.ValidationError, match="spec_version"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "version.json"))


def test_spec_rejects_dimension_parent_cycles(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    configuration["dimensions"]["machine_dimension"]["resolutions"]["machine_category"][
        "parent"
    ] = "machine"

    with pytest.raises(validation.SpecError) as error:
        spec.load_spec(_write_configuration(tmp_path, configuration, "cycle.json"))

    assert str(error.value) == (
        "dimensions.machine_dimension.resolutions.machine.parent: "
        "Dimension resolution parent cycle: machine_dimension.machine -> "
        "machine_dimension.machine_series -> machine_dimension.machine_category -> "
        "machine_dimension.machine"
    )
    assert error.value.code == "dimension_resolution_parent_cycle"
    assert error.value.path == (
        "dimensions",
        "machine_dimension",
        "resolutions",
        "machine",
        "parent",
    )


def test_spec_errors_expose_stable_profile_identity_code_and_path() -> None:
    document = spec.Spec.model_validate_json(SPEC_PATH.read_text(encoding="utf-8"))
    document.profiles["wrong"] = model.Profile(id="different")

    with pytest.raises(validation.SpecError) as error:
        validation.validate_spec(document)

    assert error.value.code == "invalid_profile_id"
    assert error.value.path == ("profiles", "wrong")
    assert str(error.value) == (
        "profiles.wrong: Profile key wrong does not match profile id different"
    )


def test_spec_rejects_unknown_write_function(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    profile = configuration["profiles"]["pump_telemetry"]
    writer_id = next(
        operator_id
        for operator_id, operator in profile["assembly"].items()
        if operator["compute"]["function"] == "write_file"
    )
    profile["assembly"][writer_id]["compute"]["function"] = "missing_write"

    with pytest.raises(ValueError, match="operators reference unknown functions: missing_write"):
        spec.load_spec(_write_configuration(tmp_path, configuration, "write.json"))


def test_spec_rejects_undeclared_binding_arguments(tmp_path: pathlib.Path) -> None:
    configuration = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    binding_args = configuration["profiles"]["pump_telemetry"]["assembly"]["read_pump_telemetry"][
        "compute"
    ]["args"]
    binding_args["unexpected"] = "value"

    with pytest.raises(
        ValueError,
        match="Binding for function read_pump_telemetry has unknown arguments: unexpected",
    ):
        spec.load_spec(_write_configuration(tmp_path, configuration, "arguments.json"))


def test_feature_references_are_explicit_and_recursive() -> None:
    args = {
        "feature": "$features.bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["$features.flow_rate", "$features.bearing_temperature"]},
    }

    binding = model.Binding(function="read", args=args)
    assert binding.resolve_args("telemetry") == {
        "feature": "bearing_temperature",
        "literal": "bearing_temperature_max",
        "nested": {"columns": ["flow_rate", "bearing_temperature"]},
    }


def test_feature_placeholder_resolves_to_bound_feature_id() -> None:
    args = {"output": "$features.@"}

    binding = model.Binding(function="calculate", args=args)
    assert binding.resolve_args("dataset", "calculated_feature") == {"output": "calculated_feature"}


def test_structural_references_compile_to_identifiers() -> None:
    args = {
        "current": "$profiles.@",
        "specific": "$profiles.pump_units",
        "dimension": "$dimensions.pump",
    }

    binding = model.Binding(function="read", args=args)
    assert binding.resolve_args("pump_telemetry") == {
        "current": "pump_telemetry",
        "specific": "pump_units",
        "dimension": "pump",
    }


def test_nested_selectors_resolve_without_changing_literal_values() -> None:
    args = {
        "nested": [
            "$profiles.@.dataset",
            {"dataset": "$profiles.other.id", "feature": "$features.@.id"},
            "$dimensions.pump.id",
            "ordinary.id",
            0,
            None,
        ]
    }

    binding = model.Binding(function="calculate", args=args)
    assert binding.resolve_args("telemetry", "calculated") == {
        "nested": [
            "telemetry",
            {"dataset": "other", "feature": "calculated"},
            "pump",
            "ordinary.id",
            0,
            None,
        ]
    }
    assert binding.profile_dependencies("telemetry") == ["telemetry"]
    assert model.Binding(function="read", args={"feature": "$features.@.id"}).resolve_args(
        "telemetry"
    ) == {"feature": "$features.@.id"}


def test_nested_model_binding_values_are_dumped_and_resolved() -> None:
    class NestedArgument(pydantic.BaseModel):
        feature: str

    binding = model.Binding(function="calculate")
    binding.args["nested"] = model.BindingArgument.model_validate(
        NestedArgument(feature="$features.flow_rate")
    )

    assert binding.resolve_args("telemetry") == {"nested": {"feature": "flow_rate"}}


def test_resolve_args_defaults_to_empty_dictionary() -> None:
    assert model.Binding(function="read").resolve_args("telemetry") == {}
