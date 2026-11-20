import hashlib
import typing

import pytest

from uptimely.spec import python as authoring
from uptimely.spec.python import conversion, dimension, merge, ref, row_context


@authoring.function(returns="any")
def calculate(value: str) -> str:
    return value


def test_dataset_subclasses_inherit_and_replace_collections() -> None:
    first = authoring.Operator(
        id="read",
        outputs=[authoring.Feature(id="value", type="float")],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
        merge=merge.default(),
    )
    replacement = authoring.Operator(
        id="read",
        outputs=[authoring.Feature(id="value", type="integer")],
        compute=authoring.Bind(
            ref.function("reader:replacement", returns="dataframe"),
        ),
        merge=merge.default(),
    )
    sink = authoring.Operator(
        id="write",
        outputs=[],
        compute=authoring.Bind(
            ref.function("writer:write", returns="none"),
            dataset=ref.dataset(),
            column=ref.feature("value"),
        ),
    )

    class Base(authoring.Profile):
        id = "base"
        description = "Inherited metadata"
        assembly = [first, sink]

    class Derived(Base):
        id = "derived"
        assembly = [replacement]

    base = Base()
    derived = Derived()
    assert base.assembly == [first, sink]
    assert derived.assembly == [replacement]
    assert list(derived.to_model().assembly) == ["read"]
    assert derived.to_model().description == "Inherited metadata"
    assert derived.to_model().features["value"].type == "integer"
    assert set(derived.function_catalog()) == {"replacement", "merge_by_grain"}


@pytest.mark.parametrize(
    ("declaration", "expected_id", "expected_name"),
    [
        (authoring.Profile(id="pump_telemetry"), "pump_telemetry", "Pump Telemetry"),
        (authoring.Profile(name="Pump Telemetry"), "pump_telemetry", "Pump Telemetry"),
        (authoring.Profile(), "profile", "Profile"),
    ],
)
def test_profile_identity_defaults(
    declaration: authoring.Profile, expected_id: str, expected_name: str
) -> None:
    assert declaration.id == expected_id
    assert declaration.name == expected_name
    assert declaration.to_model().id == expected_id


def test_profile_identity_defaults_from_subclass_name() -> None:
    class PumpAnalytics(authoring.Profile):
        pass

    declaration = PumpAnalytics()

    assert declaration.id == "pump_analytics"
    assert declaration.name == "Pump Analytics"


def test_profile_grain_supplies_dimension_resolution_metadata() -> None:
    identifier = dimension.Dimension(
        id="machine",
        description="Machine key",
        resolutions=[dimension.Resolution(id="machine", key="machine_id", type="string")],
    )

    class Example(authoring.Profile):
        id = "example"
        grain = [identifier.resolution("machine")]
        assembly = [
            authoring.Operator(
                id="values",
                outputs=[authoring.Feature(id="value", type="float")],
                compute=authoring.Bind(
                    ref.function("reader:values", returns="dataframe"),
                ),
            )
        ]

    model = Example().to_model()

    assert "machine_id" not in model.features
    assert model.identifier_types({"machine": identifier.to_model()}) == {"machine_id": "string"}
    assert model.assembly["values"].output_features == ["value"]


def test_nested_arguments_infer_inputs_without_identifier_selectors() -> None:
    operator = authoring.Operator(
        id="result",
        outputs=[authoring.Feature(id="result", type="float")],
        compute=authoring.Bind(
            ref.function("calculation:calculate", returns="dataframe"),
            configuration={
                "columns": [
                    ref.feature("first"),
                    row_context.rows(ref.feature("second"), before=2),
                    ref.feature("first"),
                ],
                "output": ref.feature("result").id,
                "key": ref.profile().grain.ids,
            },
        ),
    )
    model = operator.to_model()
    assert operator.inputs is None
    assert model.input_features == ["first", "second"]
    assert model.row_context.before.rows == 2
    assert model.compute.args["configuration"].root == {
        "columns": ["$features.first", "$features.second", "$features.first"],
        "output": "$features.result.id",
        "key": "$profiles.@.grain.ids",
    }


def test_programmatic_dataset_uses_function_name_for_catalog_id() -> None:
    operator = authoring.Operator(
        id="named",
        inputs=[ref.feature("explicit")],
        outputs=[authoring.Feature(id="result", type="float")],
        compute=authoring.Bind(
            ref.function("calculation:calculate", returns="dataframe"),
            dataset=ref.dataset(),
            column=ref.feature("inferred"),
        ),
    )
    declaration = authoring.Profile(id="example", assembly=[operator])

    assert declaration.assembly == [operator]
    assert operator.reference.entrypoint == "calculation:calculate"
    assert operator.catalog_id == "calculate"
    assert declaration.to_model().assembly["named"].input_features == ["explicit"]
    assert declaration.to_model().assembly["named"].compute.function == "calculate"
    assert set(declaration.function_catalog()) == {"calculate"}


def test_operator_inputs_accept_feature_declarations() -> None:
    operator = authoring.Operator(
        id="calculate",
        inputs=[authoring.Feature(id="explicit")],
        outputs=[authoring.Feature(id="result")],
        compute=authoring.Bind(
            ref.function("calculation:calculate", returns="dataframe"),
            value=ref.feature("inferred"),
        ),
    )

    assert operator.to_model().input_features == ["explicit"]
    assert operator.to_model().output_features == ["result"]


def test_profile_grain_selector_is_preserved_and_typed_in_python_specs() -> None:
    identifier = dimension.Dimension(
        id="machine",
        resolutions=[dimension.Resolution(id="machine", key="machine_id", type="string")],
    )
    declaration = authoring.Profile(
        id="example",
        grain=[identifier.resolution("machine")],
        assembly=[
            authoring.Operator(
                id="read",
                outputs=[authoring.Feature(id="value", type="float")],
                compute=authoring.Bind(
                    ref.function("reader:read", returns="dataframe"),
                    keys=ref.profile().grain.ids,
                    source_keys=ref.profile("source").grain.ids,
                ),
                merge=merge.default(),
            )
        ],
    )

    model = declaration.to_model()
    catalog = declaration.function_catalog()
    assert model.assembly["read"].compute.args["keys"].root == "$profiles.@.grain.ids"
    assert model.assembly["read"].compute.args["source_keys"].root == "$profiles.source.grain.ids"
    assert catalog["read"].args["keys"].type == "array[string]"
    assert catalog["read"].args["source_keys"].type == "array[string]"

    payload = conversion.to_dict(profiles=[declaration])
    assert (
        payload["profiles"]["example"]["assembly"]["read"]["compute"]["args"]["keys"]
        == "$profiles.@.grain.ids"
    )
    assert payload["functions"]["read"]["args"]["keys"]["type"] == "array[string]"


def test_mapping_constructor_requires_a_compute_binding() -> None:
    with pytest.raises(TypeError, match="required keyword-only argument: 'compute'"):
        authoring.Operator(id="read")


def test_mapping_requires_explicit_function_return_contract() -> None:
    operator = authoring.Operator(
        id="operator",
        outputs=[],
        compute=authoring.Bind(
            "reader:read",
        ),
    )
    with pytest.raises(ValueError, match="Explicit returns metadata is required"):
        operator.function_catalog()


def test_explicit_return_contract_is_preserved_without_wrapping_function() -> None:
    declaration = authoring.Operator(
        id="declaration",
        outputs=[],
        compute=authoring.Bind(
            calculate,
            value="input",
        ),
    )

    assert declaration.compute.function is calculate
    assert declaration.function_catalog()["calculate"].returns == "any"


def test_operator_export_uses_its_identifier() -> None:
    operator = authoring.Operator(
        id="operator",
        outputs=[],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
    )
    assert operator.to_model().id == "operator"


def test_operator_generates_id_from_its_single_output() -> None:
    operator = authoring.Operator(
        outputs=[authoring.Feature(id="result")],
        compute=authoring.Bind(
            ref.function("reader:read", returns="dataframe"),
        ),
    )
    prefix = "op-read-result-"
    expected_id = prefix + hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:8]

    assert operator.id == expected_id
    assert operator.to_model().id == expected_id


@pytest.mark.parametrize(
    ("outputs", "expected_id"),
    [
        ([], "op-write-features0-"),
        ([authoring.Feature(id="first"), authoring.Feature(id="second")], "op-write-features2-"),
    ],
)
def test_operator_generates_id_without_single_output(
    outputs: list[authoring.Feature], expected_id: str
) -> None:
    operator = authoring.Operator(
        outputs=outputs,
        compute=authoring.Bind(
            ref.function("writer:write", returns="none"),
        ),
    )

    assert operator.id.startswith(expected_id)
    assert operator.to_model().id == operator.id


@pytest.mark.parametrize("identifier", ["", " ", 1])
def test_operator_rejects_invalid_identifiers(identifier: typing.Any) -> None:
    with pytest.raises(ValueError, match="Operator requires a non-empty id"):
        authoring.Operator(
            id=identifier,
            outputs=[],
            compute=authoring.Bind(
                ref.function("reader:read", returns="dataframe"),
            ),
        )


@pytest.mark.parametrize("returns", ["dataframe", "none", "any"])
def test_function_catalog_records_independent_return_contract(returns: str) -> None:
    operator = authoring.Operator(
        id="work",
        outputs=[],
        compute=authoring.Bind(
            ref.function("implementation:work", returns=returns),
            dataset=ref.dataset(),
        ),
    )
    declaration = authoring.Profile(id="example", assembly=[operator])
    assert declaration.to_model().assembly["work"] == operator.to_model()
    assert declaration.function_catalog()[operator.catalog_id].returns == returns
