import dataclasses

import pytest

from uptimely.spec import model as spec_model
from uptimely.spec import python as authoring
from uptimely.spec.python import conversion, merge, ref
from uptimely.spec.validation import validate_spec


@authoring.function(returns="dataframe")
def must_not_execute(values: list[str], output: str) -> object:
    raise AssertionError("Assembly executed the implementation")


@authoring.function(returns="none")
def implementation(feature: str) -> None:
    raise AssertionError("Assembly executed the implementation")


@pytest.mark.parametrize("returns", ["dataframe", "none", "any"])
def test_operator_serialization_preserves_compute_contract(returns: str) -> None:
    operator = authoring.Operator(
        compute=authoring.Bind(ref.function("example:run", returns=returns)),
    )
    serialized = operator.to_model().model_dump()
    restored = spec_model.Operator.model_validate(serialized | {"id": operator.id})
    assert restored.compute == operator.to_model().compute
    assert restored.is_workflow == (returns != "dataframe")


def test_profile_name_defaults_to_humanized_id() -> None:
    declaration = authoring.Profile(id="pump_telemetry-dataset")

    assert declaration.name == "Pump Telemetry Dataset"
    assert declaration.to_model().name == "Pump Telemetry Dataset"


def test_seed_requires_an_explicit_operator_id_only_for_the_seed() -> None:
    generated = authoring.Operator(
        outputs=[authoring.Feature(id="other")],
        compute=authoring.Bind(ref.function("reader:read_other", returns="dataframe")),
        merge=merge.default(),
    )
    seed = authoring.Operator(
        id="initial",
        outputs=[authoring.Feature(id="value")],
        compute=authoring.Bind(ref.function("reader:read", returns="dataframe")),
    )
    declaration = authoring.Profile(id="example", seed="initial", assembly=[generated, seed])

    assert declaration.to_model().seed == "initial"
    assert generated.id in declaration.to_model().assembly
    generated_seed = authoring.Operator(
        outputs=[authoring.Feature(id="seed_value")],
        compute=authoring.Bind(ref.function("reader:seed", returns="dataframe")),
    )
    with pytest.raises(ValueError, match="explicit id"):
        authoring.Profile(id="example", seed=generated_seed.id, assembly=[generated_seed])
    with pytest.raises(ValueError, match="does not exist"):
        authoring.Profile(id="example", seed="missing", assembly=[generated])
    with pytest.raises(ValueError, match="must not have a merge"):
        authoring.Profile(
            id="example",
            seed="initial",
            assembly=[dataclasses.replace(seed, merge=merge.default())],
        )


def test_profile_seed_rejects_a_merge() -> None:
    operator = authoring.Operator(
        id="initial",
        outputs=[authoring.Feature(id="value")],
        compute=authoring.Bind(ref.function("reader:read", returns="dataframe")),
        merge=merge.default(),
    )
    with pytest.raises(ValueError, match="must not have a merge"):
        authoring.Profile(id="example", seed="initial", assembly=[operator])


def test_seed_binding_requires_a_dataframe_result() -> None:
    with pytest.raises(ValueError, match="seed operator must return a dataframe"):
        authoring.Profile(
            id="example",
            seed="initial",
            assembly=[
                authoring.Operator(
                    id="initial",
                    compute=authoring.Bind(ref.function("reader:run", returns="none")),
                )
            ],
        )


def test_fragment_bindings_require_a_merge() -> None:
    binding = authoring.Bind(ref.function("reader:read", returns="dataframe"))
    seed = authoring.Operator(id="initial", compute=binding)
    declaration = authoring.Profile(
        id="example", seed="initial", assembly=[seed, authoring.Operator(compute=binding)]
    )
    with pytest.raises(ValueError, match="must merge its result"):
        validate_spec(conversion.to_model(profiles=[declaration]))


@pytest.mark.parametrize(
    ("dataset", "message"),
    [
        ("other", "must merge its result"),
    ],
)
def test_foreign_dataframe_update_requires_merge(dataset: str | None, message: str) -> None:
    binding = authoring.Bind(
        ref.function("example:transform", returns="dataframe"),
        dataset=ref.dataset(dataset),
    )
    operator = authoring.Operator(
        compute=binding,
    )
    seed = authoring.Operator(
        id="initial", compute=authoring.Bind(ref.function("example:initial", returns="dataframe"))
    )
    with pytest.raises(ValueError, match=message):
        validate_spec(
            conversion.to_model(
                profiles=[
                    authoring.Profile(id="example", seed="initial", assembly=[seed, operator]),
                    authoring.Profile(id="other"),
                ]
            )
        )


def test_opaque_compute_cannot_merge_without_dataframe_result() -> None:
    workflow = authoring.Bind(ref.function("example:run", returns="any"))
    with pytest.raises(ValueError, match="must return a dataframe when merging"):
        authoring.Operator(compute=workflow, merge=merge.default()).function_catalog()


@pytest.mark.parametrize("invalid", ["dataframe_input", "dataframe_result", "merge"])
def test_serialized_workflow_rejects_dataframe_contracts(invalid: str) -> None:
    declaration = authoring.Profile(
        id="example",
        assembly=[
            authoring.Operator(
                id="run",
                compute=authoring.Bind(ref.function("example:run", returns="any")),
            )
        ],
    )
    document = conversion.to_dict(profiles=[declaration])
    operator = document["profiles"]["example"]["assembly"]["run"]
    function = document["functions"]["run"]
    assert operator["is_workflow"] is True
    if invalid == "dataframe_input":
        function["args"]["dataset"] = {"type": "dataframe"}
        operator["compute"]["args"]["dataset"] = "$profiles.@.dataset"
    elif invalid == "dataframe_result":
        function["returns"] = "dataframe"
    else:
        operator["merge"] = merge.default().to_model().model_dump()
    with pytest.raises(ValueError, match="Workflow cannot declare"):
        validate_spec(spec_model.Spec.model_validate(document))


@pytest.mark.parametrize(
    ("invalid", "message"),
    [
        ("unknown", "must reference an operator"),
        ("merge", "must not have a merge"),
        ("non_dataframe", "must return a dataframe"),
        ("target_input", "cannot consume its own target dataframe"),
        ("nullable_target", "cannot consume its own target dataframe"),
        ("nullable_foreign", "dataframe input must not be nullable"),
    ],
)
def test_loaded_spec_rejects_invalid_seed(invalid: str, message: str) -> None:
    declaration = authoring.Profile(
        id="example",
        assembly=[
            authoring.Operator(
                id="initial",
                outputs=[authoring.Feature(id="value")],
                compute=authoring.Bind(ref.function("reader:read", returns="dataframe")),
                merge=merge.default(),
            ),
            authoring.Operator(
                id="other",
                outputs=[authoring.Feature(id="other")],
                compute=authoring.Bind(ref.function("reader:other", returns="dataframe")),
                merge=merge.default(),
            ),
        ],
    )
    document = conversion.to_dict(profiles=[declaration])
    profile = document["profiles"]["example"]
    profile["seed"] = "missing" if invalid == "unknown" else "initial"
    seed = profile["assembly"]["initial"]
    seed.pop("merge")
    if invalid == "merge":
        seed["merge"] = profile["assembly"]["other"]["merge"]
    elif invalid == "non_dataframe":
        document["functions"][seed["compute"]["function"]]["returns"] = "none"
    elif invalid in {"target_input", "nullable_target", "nullable_foreign"}:
        document["functions"][seed["compute"]["function"]]["args"]["dataset"] = {
            "type": "dataframe" if invalid == "target_input" else "dataframe | null"
        }
        seed["compute"]["args"]["dataset"] = (
            "$profiles.foreign.dataset" if invalid == "nullable_foreign" else "$profiles.@.dataset"
        )

    with pytest.raises(ValueError, match=message):
        validate_spec(spec_model.Spec.model_validate(document))


def test_named_output_list_preserves_order_and_canonical_json_ids() -> None:
    declaration = authoring.Profile(
        id="example",
        assembly=[
            authoring.Operator(
                id="read",
                outputs=[
                    authoring.Feature(
                        id="temperature",
                        name="Ambient Temperature",
                        type="float",
                        unit="C",
                        description="Ambient temperature measurement.",
                    ),
                    authoring.Feature(id="pump", type="string"),
                ],
                compute=authoring.Bind(
                    ref.function("reader:read", returns="dataframe"),
                ),
                merge=merge.default(),
            )
        ],
    )

    canonical = declaration.to_model()
    assert list(canonical.features) == ["temperature", "pump"]
    assert canonical.features["temperature"].id == "temperature"
    assert canonical.features["temperature"].name == "Ambient Temperature"
    assert canonical.features["pump"].name == "Pump"
    assert canonical.assembly["read"].output_features == ["temperature", "pump"]
    payload = conversion.to_dict(profiles=[declaration])
    exported = payload["profiles"]["example"]
    assert exported["features"]["temperature"] == {
        "name": "Ambient Temperature",
        "type": "float",
        "unit": "C",
        "description": "Ambient temperature measurement.",
    }
    assert exported["assembly"]["read"]["interface"]["outputs"] == [
        "$features.temperature",
        "$features.pump",
    ]


def test_operator_rejects_duplicate_output_ids() -> None:
    with pytest.raises(ValueError, match="output feature IDs must not repeat"):
        authoring.Operator(
            id="operator",
            outputs=[
                authoring.Feature(id="temperature"),
                authoring.Feature(id="temperature"),
            ],
            compute=authoring.Bind(
                ref.function("reader:read", returns="dataframe"),
            ),
            merge=merge.default(),
        )


def test_assembly_collects_inputs_without_executing_implementation() -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = [
            authoring.Operator(
                id="result",
                outputs=[authoring.Feature(id="result", type="float")],
                compute=authoring.Bind(
                    must_not_execute,
                    values=[ref.feature("temperature"), ref.feature("temperature")],
                    output=ref.feature("result").id,
                ),
            )
        ]

    declaration = Example()
    operator = declaration.assembly[0]
    model = declaration.to_model().assembly["result"]

    assert model.id == "result"
    assert model.input_features == ["temperature"]
    assert operator.compute.arguments == {
        "values": [ref.feature("temperature"), ref.feature("temperature")],
        "output": ref.feature("result").id,
    }
    assert operator.bound_arguments() == operator.compute.arguments
    assert model.compute.args["output"].root == "$features.result.id"
    assert operator.outputs[0].id == "result"
    assert operator.outputs[0].name == "Result"
    assert operator.outputs[0].type == "float"


@pytest.mark.parametrize(
    "arguments",
    [{}, {"feature": "temperature", "unknown": 1}],
)
def test_assembly_defers_invalid_arguments_to_inspector(arguments: dict[str, object]) -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = [
            authoring.Operator(
                id="invalid",
                outputs=[],
                compute=authoring.Bind(
                    implementation,
                    **arguments,
                ),
            )
        ]

    model = Example().to_model()
    assert model.assembly["invalid"].compute.args.keys() == arguments.keys()


@pytest.mark.parametrize("identifier", ["result", "machine"])
def test_duplicate_producers_are_rejected(identifier: str) -> None:
    class Example(authoring.Profile):
        id = "example"
        assembly = [
            authoring.Operator(
                id="first",
                outputs=[authoring.Feature(id=identifier, type="float")],
                compute=authoring.Bind(
                    ref.function("test_declarative_authoring:implementation", returns="dataframe"),
                    output=ref.feature(identifier).id,
                ),
            )
        ]
        assembly = [*assembly, dataclasses.replace(assembly[0], id="second")]

    with pytest.raises(ValueError, match="'first' and 'second'"):
        Example().to_model()
