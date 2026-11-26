import pathlib

import pytest

from uptimely.spec import yaml as yaml_spec


def test_directory_paths_and_indexes_compose_spec(tmp_path: pathlib.Path) -> None:
    (tmp_path / "index.yaml").write_text("name: Example\n", encoding="utf-8")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "pump.yaml").write_text(
        "name: Pump\nfeatures:\n  pressure:\n    type: float\n", encoding="utf-8"
    )
    pump = profiles / "pump"
    pump.mkdir()
    (pump / "index.yml").write_text("category: Equipment\n", encoding="utf-8")
    (pump / "features.yaml").write_text("pressure:\n  type: float\n  unit: bar\n", encoding="utf-8")
    (pump / "grain.yaml").write_text("[]\n", encoding="utf-8")

    document = yaml_spec.load_spec(tmp_path, validate=False)

    assert document.name == "Example"
    assert document.profiles["pump"].category == "Equipment"
    assert document.profiles["pump"].features["pressure"].unit == "bar"
    assert document.profiles["pump"].grain == []


@pytest.mark.parametrize(
    ("first", "second"),
    [("value: [1, 2]\n", "value: [2, 1]\n"), ("value: true\n", "value: 1\n")],
)
def test_conflicting_fragments_report_both_files(
    tmp_path: pathlib.Path, first: str, second: str
) -> None:
    original = tmp_path / "index.yaml"
    original.write_text(f"profiles:\n  pump:\n    {first}", encoding="utf-8")
    path = tmp_path / "profiles"
    path.mkdir()
    other = path / "pump.yaml"
    other.write_text(second, encoding="utf-8")

    with pytest.raises(ValueError, match=r"profiles\.pump\.value") as error:
        yaml_spec.load_document(tmp_path)
    assert str(original) in str(error.value)
    assert str(other) in str(error.value)


@pytest.mark.parametrize(
    "content",
    [
        "name: one\nname: two\n",
        "name: !!python/object/apply:os.system ['echo unsafe']\n",
        "name: 2026-01-01\n",
        "name: .inf\n",
        "1: value\n",
    ],
)
def test_invalid_yaml_values_include_source_path(tmp_path: pathlib.Path, content: str) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="spec.yaml"):
        yaml_spec.load_document(source)


def test_yaml_aliases_and_yaml_12_scalars(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text("first: &value [on, off]\nsecond: *value\n", encoding="utf-8")
    document = yaml_spec.load_document(source)
    assert document == {"first": ["on", "off"], "second": ["on", "off"]}
    document["first"].append("other")
    assert document["second"] == ["on", "off"]


def test_recursive_yaml_alias_fails(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text("value: &recursive [*recursive]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="recursive"):
        yaml_spec.load_document(source)


def test_concise_operator_infers_contract_and_feature_interfaces(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
profiles:
  summary:
    grain: [machine.pump]
    assembly:
      aggregate:
        function: pump_analytics:aggregate
        input: readings
        merge: default
        args:
          aggregations:
            "$input.temperature": max
          dimensions: [pump_id]
          rename:
            temperature: "$output.maximum"
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    profile = document.profiles["summary"]
    operator = profile.assembly["aggregate"]

    assert profile.grain[0].dimension == "machine"
    assert profile.grain[0].resolution == "pump"
    assert operator.input_features == ["temperature"]
    assert operator.output_features == ["maximum"]
    assert "maximum" in profile.features
    assert operator.compute.args["dataset"].root == "$profiles.readings.dataset"
    assert operator.compute.args["aggregations"].root == {"temperature": "max"}
    assert operator.compute.args["rename"].root == {"temperature": "$features.maximum"}
    assert operator.merge is not None
    assert operator.merge.function == "merge_by_grain"
    function = document.functions["aggregate"]
    assert function.entrypoint == "pump_analytics:aggregate"
    assert function.returns == "dataframe"
    assert function.args["dataset"].type == "dataframe"


def test_concise_operator_supports_explicit_function_alias(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
functions:
  my_aggregate:
    entrypoint: pump_analytics:aggregate
    returns: dataframe
    args:
      dataset: {type: dataframe}
      aggregations: {type: "object{str: string}"}
      dimensions: {type: "array[string]"}
      rename: {type: "object{str: string}"}
profiles:
  summary:
    assembly:
      calculate:
        function: my_aggregate
        input: readings
        inputs: [temperature]
        outputs: [maximum]
        args:
          aggregations: {temperature: max}
          dimensions: [pump_id]
          rename: {temperature: maximum}
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    assert document.profiles["summary"].assembly["calculate"].compute.function == "my_aggregate"
    assert document.functions["my_aggregate"].entrypoint == "pump_analytics:aggregate"


def test_feature_metadata_reference_is_not_a_data_dependency(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
profiles:
  summary:
    features:
      temperature: {}
    assembly:
      extract:
        function: pump_analytics:extract_field
        args:
          column: "$input.temperature"
          field: "$features.metadata.name"
          output: "$output.value"
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    assert document.profiles["summary"].assembly["extract"].input_features == ["temperature"]


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("function: builtins:len\ninput: readings", "Cannot determine the single dataframe"),
        (
            "function: pump_analytics:aggregate\nargs:\n  aggregations:\n"
            '    "$input.temperature": max\n    temperature: min',
            "Duplicate argument key",
        ),
    ],
)
def test_concise_operator_reports_invalid_declarations(
    tmp_path: pathlib.Path, body: str, message: str
) -> None:
    source = tmp_path / "spec.yaml"
    indented = "\n".join(f"        {line}" for line in body.splitlines())
    source.write_text(
        f"profiles:\n  summary:\n    assembly:\n      calculate:\n{indented}\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=message):
        yaml_spec.load_spec(source, validate=False)


def test_concise_operator_reports_function_id_collision(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
functions:
  aggregate:
    entrypoint: pump_io:read_file
    returns: dataframe
profiles:
  summary:
    assembly:
      calculate:
        function: pump_analytics:aggregate
        input: readings
        args:
          aggregations: {"$input.temperature": max}
          dimensions: [pump_id]
          rename: {temperature: "$output.maximum"}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"summary\.assembly\.calculate.*Conflicting function"):
        yaml_spec.load_spec(source, validate=False)


def test_dataframe_source_inference_uses_all_profile_outputs(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
profiles:
  summary:
    assembly:
      select:
        function: pump_analytics:select_columns
        args:
          columns: ["$input.temperature"]
          rename: {temperature: "$output.maximum"}
      write:
        function: pump_io:write_file
        args:
          features: ["$input.maximum"]
          output: result.csv
  readings:
    assembly:
      read:
        function: pump_io:read_file
        outputs: [temperature]
        args:
          source: readings.csv
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    operators = document.profiles["summary"].assembly
    assert operators["select"].compute.args["dataset"].root == "$profiles.readings.dataset"
    assert operators["write"].compute.args["dataset"].root == "$profiles.@.dataset"
    assert document.profiles["readings"].features["temperature"].id == "temperature"


def test_dataframe_source_uses_explicit_inputs_and_ignores_keys(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
dimensions:
  machine:
    resolutions:
      pump: {key: pump_id, type: string}
profiles:
  readings:
    grain: [machine.pump]
    features:
      temperature: {}
  summary:
    assembly:
      select:
        function: pump_analytics:select_columns
        inputs: [pump_id, temperature]
        args:
          columns: [pump_id, temperature]
          rename: {}
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    binding = document.profiles["summary"].assembly["select"].compute
    assert binding.args["dataset"].root == "$profiles.readings.dataset"


def test_dataframe_source_uses_inferred_output_in_later_profile(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
profiles:
  summary:
    assembly:
      select:
        function: pump_analytics:select_columns
        args:
          columns: ["$input.temperature"]
          rename: {}
  readings:
    assembly:
      select:
        function: pump_analytics:extract_field
        args:
          dataset: "$profiles.raw.dataset"
          column: value
          field: temperature
          output: "$output.temperature"
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    assert (
        document.profiles["summary"].assembly["select"].compute.args["dataset"].root
        == "$profiles.readings.dataset"
    )


@pytest.mark.parametrize(
    ("profiles", "inputs", "detail"),
    [
        ("", "[]", "no non-key input features"),
        ("", "[temperature]", "temperature: no owner"),
        (
            "  readings: {features: {temperature: {}}}\n"
            "  duplicate: {features: {temperature: {}}}\n",
            "[temperature]",
            "temperature: readings, duplicate",
        ),
        (
            "  readings: {features: {temperature: {}}}\n  other: {features: {pressure: {}}}\n",
            "[temperature, pressure]",
            "temperature: readings, pressure: other",
        ),
    ],
)
def test_unresolved_dataframe_source_requires_explicit_binding(
    tmp_path: pathlib.Path, profiles: str, inputs: str, detail: str
) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        f"""profiles:
{profiles}  summary:
    assembly:
      select:
        function: pump_analytics:select_columns
        inputs: {inputs}
        args:
          columns: []
          rename: {{}}
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match=r"profiles\.summary\.assembly\.select") as error:
        yaml_spec.load_spec(source, validate=False)
    assert detail in str(error.value)
    assert "Bind args.dataset explicitly" in str(error.value)


def test_explicit_dataframe_argument_needs_no_inferred_source(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
profiles:
  summary:
    assembly:
      select:
        function: pump_analytics:select_columns
        args:
          dataset: "$profiles.readings.dataset"
          columns: []
          rename: {}
""",
        encoding="utf-8",
    )
    document = yaml_spec.load_spec(source, validate=False)
    binding = document.profiles["summary"].assembly["select"].compute
    assert binding.args["dataset"].root == "$profiles.readings.dataset"


def test_multiple_dataframe_arguments_require_explicit_bindings(tmp_path: pathlib.Path) -> None:
    source = tmp_path / "spec.yaml"
    source.write_text(
        """
functions:
  combine:
    entrypoint: pump_analytics:select_columns
    returns: dataframe
    validate_signature: false
    args:
      left: {type: dataframe}
      right: {type: dataframe}
profiles:
  summary:
    assembly:
      combine:
        function: combine
""",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Cannot determine the single dataframe argument"):
        yaml_spec.load_spec(source, validate=False)
