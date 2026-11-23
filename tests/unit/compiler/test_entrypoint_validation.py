import collections
import logging
import pathlib
import sys
from collections import abc

import pytest
from support import examples as example_support

from uptimely import application, compiler, spec
from uptimely import plan as plan
from uptimely.codebase.python import entrypoint as shared_entrypoint
from uptimely.explorer.sections import spec as spec_render
from uptimely.inspector import BindingInspection

SPEC_PATH = example_support.EXAMPLES_ROOT / "artifacts/build/spec.json"


pytestmark = pytest.mark.usefixtures("example_projects")


@pytest.fixture(autouse=True)
def isolate_package_index() -> abc.Iterator[None]:
    """Keep mocked distribution indexes separate from real environment metadata."""
    shared_entrypoint.PackageOrigin.invalidate_cache()
    yield
    shared_entrypoint.PackageOrigin.invalidate_cache()


def test_compiler_rejects_string_feature_selection() -> None:
    with pytest.raises(ValueError, match="features must be a collection"):
        compiler.Compiler().compile(spec.load_spec(SPEC_PATH), features="health_signal_normalized")


def test_compiler_does_not_depend_on_installed_package_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_package_lookup(self: shared_entrypoint.Entrypoint) -> shared_entrypoint.PackageOrigin:
        pytest.fail("Compilation must not inspect entrypoint package metadata")

    monkeypatch.setattr(shared_entrypoint.Entrypoint, "read_package", fail_package_lookup)
    compiled = compiler.Compiler().compile(spec.load_spec(SPEC_PATH))

    assert compiled.invocations
    assert plan.from_dict(plan.to_dict(compiled)) == compiled


def test_compiler_lowers_merge_bindings_to_publication_invocations() -> None:
    specification = spec.load_spec(SPEC_PATH)
    compiled = compiler.Compiler().compile(specification)
    compute_by_operator = {
        (invocation.semantics.profile_id, invocation.semantics.operator_id): invocation
        for invocation in compiled.invocations
        if invocation.semantics.role == "compute"
    }
    merges_by_operator = {
        (invocation.semantics.profile_id, invocation.semantics.operator_id): invocation
        for invocation in compiled.invocations
        if invocation.semantics.role == "merge"
    }

    assert merges_by_operator
    assert set(merges_by_operator) == {
        key for key, operator in specification.operator_items if operator.merge is not None
    }
    assert set(compute_by_operator) >= set(merges_by_operator)
    for operator_key, merge in merges_by_operator.items():
        compute = compute_by_operator[operator_key]
        assert compute.id in merge.semantics.dependency_ids
        profile_key = specification.profile_keys[compute.semantics.profile_id]
        assert (
            compute.semantics.target_identifiers
            == specification.identifiers_by_profile[profile_key]
        )
        assert set(compute.semantics.output_types) == set(compute.semantics.output_features)
        assert merge.semantics.target_identifiers == compute.semantics.target_identifiers
        assert merge.semantics.fragment_keys == compute.semantics.fragment_keys
        assert merge.semantics.result == "target"
        assert merge.semantics.role == "merge"
        assert merge.semantics.output_features == []
        assert merge.semantics.output_types == {}
        assert merge.semantics.dataframe_input_scope == "unrestricted"
        assert merge.semantics.fragment_dimensions == "not_applicable"
        assert merge.semantics.row_count_relation == "unrestricted"
        assert merge.semantics.key_relation == "unrestricted"
        assert merge.semantics.row_order_relation == "unrestricted"
        assert merge.semantics.existing_data_relation == "unrestricted"
        assert compute.semantics.result == "fragment"
        assert compute.semantics.output_features
    target_transform = next(
        invocation
        for invocation in compiled.invocations
        if invocation.semantics.dataframe_input_scope == "target"
    )
    assert target_transform.semantics.row_count_relation == "same"
    assert target_transform.semantics.key_relation == "identical"
    assert target_transform.semantics.row_order_relation == "preserve"
    assert target_transform.semantics.existing_data_relation == "preserve"
    assert all(
        len(
            {
                (producer.semantics.profile_id, producer.semantics.operator_id)
                for producer in producers
            }
        )
        == len(producers)
        for producers in compiled.features.values()
    )

    feature_producers = {
        feature: invocation
        for invocation in compiled.invocations
        if invocation.semantics.role == "compute"
        for feature in invocation.semantics.output_features
    }
    for invocation in compiled.invocations:
        if invocation.semantics.role == "merge":
            continue
        for feature in invocation.semantics.input_features:
            producer = feature_producers.get(feature)
            if (
                producer is None
                or producer.semantics.operator_id == invocation.semantics.operator_id
            ):
                continue
            publication = merges_by_operator.get(
                (producer.semantics.profile_id, producer.semantics.operator_id), producer
            )
            assert publication.id in invocation.semantics.dependency_ids

    selected_feature = next(
        feature for feature in feature_producers if feature not in specification.identifier_ids
    )
    selected = compiler.Compiler().compile(specification, features=[selected_feature])
    selected_producer = feature_producers[selected_feature]
    selected_merge = merges_by_operator.get(
        (selected_producer.semantics.profile_id, selected_producer.semantics.operator_id)
    )
    if selected_merge is not None:
        assert selected_merge.id in {invocation.id for invocation in selected.invocations}
    assert any(
        selected_feature in invocation.semantics.output_features
        for invocation in selected.invocations
    )


@pytest.mark.parametrize(
    ("category", "function_id"),
    [("vectorize", "ratio"), ("collapse", "aggregate")],
)
def test_compiler_rejects_missing_function_entrypoints(
    category: str, function_id: str, caplog: pytest.LogCaptureFixture
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions[function_id].entrypoint = ""
    expected_invocations = sum(
        1 + (operator.merge is not None) for operator in spec_definition.operators
    )
    caplog.set_level(logging.DEBUG, logger="uptimely.compiler")

    with pytest.raises(
        ValueError, match=f"Missing entrypoint for function {function_id} used by operator "
    ):
        compiler.Compiler().compile(spec_definition)

    assert f"Validating {expected_invocations} invocations" in caplog.messages
    assert caplog.messages.count("Validate function entrypoint declarations") == 1
    assert not any(message.startswith("\nCompiler operator:") for message in caplog.messages)


@pytest.mark.parametrize("level", [logging.DEBUG, logging.INFO])
def test_compiler_summarizes_invocation_checks_once(
    caplog: pytest.LogCaptureFixture, pump_bundle: application.BuildBundle, level: int
) -> None:
    caplog.set_level(level, logger="uptimely")
    compiler_instance = compiler.Compiler()

    compiled = compiler_instance.compile(pump_bundle.spec_definition)
    summaries = [message for message in caplog.messages if message.startswith("Validating ")]
    assert summaries == (
        [f"Validating {len(compiled.invocations)} invocations"] if level == logging.DEBUG else []
    )
    for check in (
        "Validate function entrypoint declarations",
        "Select unique functions for implementation checks",
        "Create portable invocations",
    ):
        assert caplog.messages.count(check) == (1 if level == logging.DEBUG else 0)
    assert not any(message.startswith("\nCompiler operator:") for message in caplog.messages)
    assert all("\n" not in message and message == message.lstrip() for message in caplog.messages)
    assert not any(message.startswith("\nCompiler function:") for message in caplog.messages)


def test_explorer_context_reports_unloadable_function_modules() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["ratio"].entrypoint = "uptimely_test_missing_dependency:calculate"

    with pytest.raises(ModuleNotFoundError, match="uptimely_test_missing_dependency"):
        spec_render._build_context(spec_definition, False)


def test_compiler_skips_disabled_signatures_without_changing_dependencies(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch, pump_bundle: application.BuildBundle
) -> None:
    spec_definition = pump_bundle.spec_definition
    baseline = pump_bundle.execution_plan
    package_name = f"signature_fixture_{tmp_path.name.replace('-', '_')}"
    package = tmp_path / package_name
    package.mkdir()
    marker = tmp_path / "imported"
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "calculation.py").write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
        "import uptimely_test_missing_dependency\n"
        "def calculate():\n    return None\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    function = spec_definition.functions["ratio"]
    function.entrypoint = f"{package_name}.calculation:calculate"
    function.validate_signature = False

    signatures = BindingInspection.inspect_spec(spec_definition)
    compiled = compiler.Compiler().compile(spec_definition, signatures=signatures)

    assert not marker.exists()
    assert package_name not in sys.modules
    assert [set(stage) for stage in compiled.stages] == [set(stage) for stage in baseline.stages]
    assert len(compiled.invocations) == len(baseline.invocations)
    baseline_invocations = {node.id: node for node in baseline.invocations}
    assert {node.id for node in compiled.invocations} == set(baseline_invocations)
    for actual in compiled.invocations:
        expected = baseline_invocations[actual.id]
        assert set(actual.semantics.dependency_ids) == set(expected.semantics.dependency_ids)
        assert actual.semantics.input_features == expected.semantics.input_features
        assert actual.semantics.output_features == expected.semantics.output_features
        if actual.semantics.function_id == function.id:
            assert actual.entrypoint == function.entrypoint
            assert actual.semantics.return_type is None
        else:
            assert actual.semantics.return_type == expected.semantics.return_type

    function.validate_signature = True
    with pytest.raises(ValueError) as exc_info:
        BindingInspection.inspect_spec(spec_definition)
    message = str(exc_info.value)
    assert "Could not read signature" in message
    assert "uptimely_test_missing_dependency" in message


def test_compiler_still_validates_spec_when_signature_validation_is_disabled() -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    spec_definition.functions["ratio"].validate_signature = False
    profile = spec_definition.profiles["pump_telemetry"]
    operator = profile.assembly[
        example_support.operator_id_for_output(profile.assembly, "pressure_flow_efficiency")
    ]
    operator.interface.inputs = ["$features.missing_input"]
    spec_definition = spec.Spec.model_validate(spec_definition.model_dump())

    with pytest.raises(ValueError, match="unknown input feature"):
        compiler.Compiler().compile(spec_definition)


def test_compiler_instance_can_compile_independent_specs_and_selections() -> None:
    compiler_instance = compiler.Compiler()
    spec_definition = spec.load_spec(SPEC_PATH)

    complete = compiler_instance.compile(spec_definition)
    selected = compiler_instance.compile(spec_definition, features=["health_signal_normalized"])

    assert len(complete.invocations) > len(selected.invocations)
    assert any(
        "health_signal_normalized" in invocation.semantics.output_features
        for invocation in selected.invocations
    )


@pytest.mark.parametrize("validate_signature", [False, True])
def test_compiler_checks_entrypoint_syntax_when_signature_validation_is_disabled(
    validate_signature: bool,
) -> None:
    spec_definition = spec.load_spec(SPEC_PATH)
    function = spec_definition.functions["ratio"]
    function.entrypoint = "invalid-entrypoint"
    function.validate_signature = validate_signature

    with pytest.raises(
        ValueError,
        match="Invalid entrypoint 'invalid-entrypoint'",
    ):
        compiler.Compiler().compile(spec_definition)


def test_inspector_inspects_each_distinct_entrypoint_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reads: collections.Counter[str] = collections.Counter()
    original_read = shared_entrypoint.Signature.read

    def read(
        cls: type[shared_entrypoint.Signature], function: shared_entrypoint.Function
    ) -> shared_entrypoint.Signature:
        reads[f"{function.module.location}:{function.name}"] += 1
        return original_read(function)

    monkeypatch.setattr(shared_entrypoint.Signature, "read", classmethod(read))

    document = spec.load_spec(SPEC_PATH)
    inspected = BindingInspection.inspect_spec(document)
    compiled = compiler.Compiler().compile(document, signatures=inspected)

    assert inspected
    assert reads
    assert all(count == 1 for count in reads.values())
    restored = plan.from_dict(plan.to_dict(compiled))
    assert {node.entrypoint for node in restored.invocations} == {
        node.entrypoint for node in compiled.invocations
    }
