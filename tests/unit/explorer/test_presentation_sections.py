import copy
import json

import graphable
import pytest
from graphable import views

from uptimely import plan as execution_plan
from uptimely import spec
from uptimely.explorer import common
from uptimely.explorer.sections import data_lineage, feature_lineage, invocation_lineage
from uptimely.explorer.sections import plan as plan_render
from uptimely.explorer.sections import spec as spec_render
from uptimely.spec import model, operator_kinds
from uptimely.spec.feature_graph import feature_graph, models


def test_optional_field_filter_preserves_falsy_values() -> None:
    assert common.filled_fields(
        absent=None, flag=False, count=0, text="", items=[], metadata={}
    ) == {"flag": False, "count": 0, "text": "", "items": [], "metadata": {}}


def test_stage_arguments_include_compiled_function_data_types() -> None:
    argument_types = {"source": "string", "dataset": "dataframe", "columns": "array[string]"}
    arguments = {
        "source": "$params.source",
        "dataset": "$dataframes.data",
        "columns": ["reading"],
    }
    definition = spec.Spec.model_validate(
        {
            "functions": {
                "calculate": {
                    "returns": "dataframe",
                    "entrypoint": "example:calculate",
                    "args": {name: {"type": value} for name, value in argument_types.items()},
                }
            },
            "profiles": {"data": {"features": {"reading": {"type": "float"}}}},
        }
    )
    invocation = execution_plan.Invocation(
        role="compute",
        result="target",
        id="calculate",
        operator_kind="vectorize",
        entrypoint="example:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="data",
        arguments=arguments,
        argument_types=argument_types,
    )
    compiled = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[invocation],
        stages=[["calculate"]],
    )

    step = plan_render._build_step(1, invocation, compiled, definition)

    assert {name: argument["type"]["function"] for name, argument in step["args"].items()} == (
        argument_types
    )
    assert {name: argument["value"] for name, argument in step["args"].items()} == arguments


def test_merge_invocations_expose_phase_binding_and_fragment_edge() -> None:
    definition = spec.Spec.model_validate(
        {
            "functions": {
                "read": {
                    "returns": "dataframe",
                    "entrypoint": "example:read",
                },
                "join": {
                    "returns": "dataframe",
                    "entrypoint": "example:join",
                    "args": {
                        "target": {"type": "dataframe | null"},
                        "fragment": {"type": "dataframe"},
                        "dataset_keys": {"type": "array[string]"},
                    },
                },
            },
            "profiles": {"data": {"features": {"value": {"type": "float"}}}},
        }
    )
    read_id = "invocation:read:read:data:source"
    merge_id = "invocation:merge:join:data:source"
    read = execution_plan.Invocation(
        role="compute",
        result="fragment",
        id=read_id,
        operator_kind="read",
        fragment_dimensions="target",
        entrypoint="example:read",
        function_id="read",
        operator_id="source",
        profile_id="data",
        output_features=["value"],
    )
    merge = execution_plan.Invocation(
        result="target",
        id=merge_id,
        operator_kind="merge",
        role="merge",
        entrypoint="example:join",
        function_id="join",
        operator_id="source",
        profile_id="data",
        arguments={
            "dataset": "data",
            "fragment": "$operators.source.fragment",
            "dataset_keys": ["id"],
        },
        dependency_ids=[read_id],
    )
    compiled = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[read, merge],
        stages=[[read_id], [merge_id]],
    )

    nodes, links = invocation_lineage.invocation_lineage_payload(compiled, definition)
    context = plan_render.build_context(compiled, definition)
    card = context["stages"][1]["steps"][0]
    merge_node = next(node for node in nodes if node["id"] == merge_id)

    assert merge_node["phase"] == card["phase"] == "merge"
    assert merge_node["operator_id"] == card["operator_id"] == "source"
    assert merge_node["operator_name"] == "Source"
    assert merge_node["merge_dataset"] == card["merge_dataset"] == "data"
    assert merge_node["fragment_source"] == card["fragment_source"] == "$operators.source.fragment"
    assert merge_node["merge_keys"] == card["merge_keys"] == ["id"]
    assert all(node["profile_id"] == "data" for node in nodes)
    assert all(node["profile_name"] == "Data" for node in nodes)
    assert all("dataset_id" not in node and "dataset_name" not in node for node in nodes)
    assert links == [{"source": read_id, "target": merge_id, "dependency_type": "fragment"}]


def test_graph_payload_serialization_is_stable_and_script_safe() -> None:
    payload = common.serialize_graph_payload(
        nodes=[{"id": "z", "label": "</script>"}, {"id": "a", "label": "first"}],
        links=[{"source": "z", "target": "z"}, {"source": "a", "target": "z"}],
    )

    assert payload == (
        r'{"nodes": [{"id": "a", "label": "first"}, {"id": "z", "label": "<\/script>"}], '
        '"links": [{"source": "a", "target": "z"}, {"source": "z", "target": "z"}]}'
    )


def test_feature_labels_use_ids_for_empty_names_and_prefer_global_dimensions() -> None:
    definition = spec.Spec.model_validate(
        {
            "dimensions": {
                "id": {
                    "name": "Global key",
                    "resolutions": {"default": {"key": "id", "type": "integer"}},
                }
            },
            "profiles": {
                "data": {
                    "features": {
                        "id": {"name": "Dataset key"},
                        "value": {"name": ""},
                    }
                }
            },
        }
    )
    assert common.feature_labels(definition) == {"id": "Global key", "value": "value"}


def test_feature_data_preserves_empty_strings() -> None:
    node = models.FeatureNode(name="reading", data_type="", profile_id="telemetry")

    assert feature_lineage._node_data(node) == {
        "node_type": "feature",
        "is_operator": False,
        "label": "reading",
        "feature_id": "reading",
        "profile": "telemetry",
        "profile_id": "telemetry",
        "data_type": "",
    }


@pytest.mark.parametrize("kind", ["read", "vectorize"])
def test_lineage_preserves_declared_feature_types_for_all_producers(kind: str) -> None:
    definition = spec.Spec.model_validate(
        {
            "functions": {
                "calculate": {
                    "returns": "dataframe",
                    "entrypoint": "example:calculate",
                    "args": {"dataset": {"type": "dataframe"}} if kind == "vectorize" else {},
                }
            },
            "profiles": {
                "data": {
                    "features": {"reading": {"type": "float"}},
                    "assembly": {
                        "calculate": {
                            "compute": {
                                "function": "calculate",
                                "args": {"dataset": "$profiles.data.dataset"}
                                if kind == "vectorize"
                                else {},
                            },
                            "interface": {"outputs": ["$features.reading"]},
                        }
                    },
                }
            },
        }
    )
    graph = spec.FeatureGraph(definition, validate=False)
    for selected in (graph, graph.subset(["reading"])):
        nodes, _ = feature_lineage.feature_lineage_payload(selected)
        reading = next(node for node in nodes if node["id"] == "reading")
        assert reading["data_type"] == "float"
        operator_node = next(node for node in nodes if node.get("is_operator"))
        assert operator_node["operator_kind"] == kind


def test_catalog_groups_callables_by_category_and_labels_each_operator_usage() -> None:
    definition = spec.Spec.model_validate(
        {
            "functions": {
                "calculate": {
                    "returns": "dataframe",
                    "category": "Analysis",
                    "entrypoint": "unavailable_example:calculate",
                    "validate_signature": False,
                    "args": {"dataset": {"type": "dataframe"}},
                },
                "unused": {
                    "returns": "any",
                    "entrypoint": "unavailable_example:unused",
                    "validate_signature": False,
                },
            },
            "profiles": {
                "local": {
                    "features": {"value": {}},
                    "assembly": {
                        "calculate": {
                            "compute": {
                                "function": "calculate",
                                "args": {"dataset": "$profiles.local.dataset"},
                            },
                            "interface": {"outputs": ["$features.value"]},
                        }
                    },
                },
                "foreign": {
                    "features": {"copied": {}},
                    "assembly": {
                        "copy": {
                            "compute": {
                                "function": "calculate",
                                "args": {"dataset": "$profiles.local.dataset"},
                            },
                            "interface": {
                                "inputs": ["$features.value"],
                                "outputs": ["$features.copied"],
                            },
                        }
                    },
                },
            },
        }
    )

    context = spec_render.build_context(spec_render._build_context(definition, False))
    configuration = context["configuration"]

    assert set(context["function_groups"]) == {"Analysis", "Uncategorized"}
    assert context["summary"]["function_buckets"] == {"Analysis": 1, "Uncategorized": 1}
    assert configuration["functions"]["calculate"]["operator_usage_count"] == 2
    assert configuration["functions"]["calculate"]["declared_returns"] == "dataframe"
    assert all("kind" not in function for function in configuration["functions"].values())
    assert configuration["profiles"]["local"]["assembly"]["calculate"]["kind"] == "vectorize"
    assert configuration["profiles"]["foreign"]["assembly"]["copy"]["kind"] == "conform"
    assert context["summary"]["feature_buckets"] == {
        "input": 1,
        "intermediate": 0,
        "output": 1,
    }


def test_operator_data_includes_declared_function_metadata() -> None:
    function = model.FunctionTemplate(
        id="double",
        returns="dataframe",
        description="Double a reading",
        entrypoint="example:double",
    )
    node = models.OperatorNode(
        operator_id="double_operator",
        features=("doubled",),
        profile_id="telemetry",
        function=function,
        operator_kind="vectorize",
    )

    assert feature_lineage._node_data(node) == {
        "node_type": "feature",
        "is_operator": True,
        "label": "Double",
        "operator_id": "double_operator",
        "features": ["doubled"],
        "profile": "telemetry",
        "profile_id": "telemetry",
        "function_id": "double",
        "function_name": "Double",
        "operator_kind": "vectorize",
        "is_effect": False,
        "type": "python_function",
        "entrypoint": "example:double",
        "info": {"description": "Double a reading"},
    }


def test_feature_payload_preserves_graph_metadata_and_excludes_external_edges() -> None:
    source = graphable.graphable.Graphable(models.FeatureNode(name="source", display_name="Source"))
    output = graphable.graphable.Graphable(models.FeatureNode(name="output"))
    graph = graphable.graph.Graph()
    graph.add_edge(source, output)
    full = feature_graph.FeatureSubGraph(graph, ["output"])
    subset = feature_graph.FeatureSubGraph(graphable.graph.Graph([source], discover=False), [])
    config = views.CytoscapeStylingConfig(
        reference_fnc=lambda node: node.reference.node_id,
        node_data_fnc=lambda node: feature_lineage._node_data(node.reference),
    )
    for selected in (full, subset):
        elements = json.loads(views.create_topology_cytoscape(selected.graph, config))
        expected_nodes = [
            element["data"] for element in elements if "source" not in element["data"]
        ]
        expected_links = [
            {"source": element["data"]["source"], "target": element["data"]["target"]}
            for element in elements
            if "source" in element["data"]
        ]
        assert feature_lineage.feature_lineage_payload(selected) == (expected_nodes, expected_links)
    assert feature_lineage.feature_lineage_payload(subset)[1] == []


def test_main_columns_replace_outputs_in_order_without_materializing_escape() -> None:
    empty_plan = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[],
        stages=[],
    )
    builder = data_lineage._DataLineageBuilder(spec.Spec(), empty_plan)
    invocation = execution_plan.Invocation(
        role="compute",
        result="target",
        id="calculate",
        operator_kind="vectorize",
        entrypoint="example:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="data",
        input_features=["a"],
    )
    a, b, c = [
        data_lineage.DataLineageColumn(name, "float", "Output", "red", 1)
        for name in ("a", "b", "c")
    ]
    assert builder._main_columns(invocation, [a, b]) == [a, b]
    assert builder._main_columns(invocation, [a, c]) == [
        copy.replace(b, role="Existing"),
        a,
        c,
    ]
    escape = copy.replace(invocation, operator_kind="escape")
    assert builder._main_columns(escape, [b]) == [
        copy.replace(a, role="Input"),
        copy.replace(b, role="Existing"),
        copy.replace(c, role="Existing"),
    ]


@pytest.mark.parametrize(
    ("kind_id", "card_feature", "topology_feature", "effect", "target_rows", "source_rows"),
    [
        ("read", None, None, False, 3, 3),
        ("write", None, None, False, 3, 3),
        ("escape", "Value", "Value", True, 3, 3),
        ("conform", None, None, False, 3, 3),
        ("expand", None, None, False, 3, 1),
        ("collapse", "Value", None, False, 1, 3),
        ("vectorize", "Value", "Value", False, 3, 3),
    ],
)
def test_kind_capabilities_preserve_presentation_contracts(
    kind_id: operator_kinds.OperatorKindId,
    card_feature: str | None,
    topology_feature: str | None,
    effect: bool,
    target_rows: int,
    source_rows: int,
) -> None:
    definition = spec.Spec.model_validate(
        {
            "functions": {
                "calculate": {
                    "returns": operator_kinds.OPERATOR_KINDS[kind_id].returns,
                    "entrypoint": "example:calculate",
                }
            },
            "profiles": {
                "data": {"features": {"value": {}}},
                "source": {"features": {"raw": {}}},
            },
        }
    )
    invocation = execution_plan.Invocation(
        role="compute",
        result="target",
        id="calculate",
        operator_kind=kind_id,
        entrypoint="example:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="data",
        input_features=["raw"],
        output_features=["value"],
    )
    compiled = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[invocation],
        stages=[["calculate"]],
    )
    card = plan_render._build_step(1, invocation, compiled, definition)
    nodes, _ = invocation_lineage.invocation_lineage_payload(compiled, definition)
    step = data_lineage._build_stages(definition, compiled)[0][0]
    assert card["feature"] == card_feature
    assert card["uncontrolled"] is effect
    assert nodes[0]["feature"] == topology_feature
    assert nodes[0]["is_effect"] is effect
    assert step.row_count == target_rows
    assert [column.role for column in step.columns] == [
        "Declared input" if effect else "Input",
        "Output",
    ]
    if effect:
        assert step.input_tables == []
        assert step.main_columns == []
    else:
        assert step.input_tables[0].row_count == source_rows
        assert [column.name for column in step.main_columns] == ["value"]


def test_presentation_follows_changed_capabilities_not_kind_names(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = spec.Spec.model_validate(
        {
            "functions": {
                "calculate": {
                    "returns": "dataframe",
                    "entrypoint": "example:calculate",
                }
            },
            "profiles": {
                "data": {"features": {"value": {}}},
            },
        }
    )
    invocation = execution_plan.Invocation(
        role="compute",
        result="target",
        id="calculate",
        operator_kind="read",
        entrypoint="example:calculate",
        function_id="calculate",
        operator_id="calculate",
        profile_id="data",
        output_features=["value"],
    )
    compiled = execution_plan.ExecutionPlan(
        plan_version=execution_plan.PLAN_VERSION,
        required_backend="polars",
        invocations=[invocation],
        stages=[["calculate"]],
    )
    catalog = dict(operator_kinds.OPERATOR_KINDS)
    catalog["read"] = copy.replace(
        catalog["read"], is_effect=True, is_transformer=True, dimension_change="remove"
    )
    monkeypatch.setattr(operator_kinds, "OPERATOR_KINDS", catalog)

    context = plan_render.build_context(compiled, definition)
    card = context["stages"][0]["steps"][0]
    node = json.loads(context["invocation_lineage_data"])["nodes"][0]
    step = data_lineage._build_stages(definition, compiled)[0][0]
    assert card["feature"] == "Value"
    assert card["uncontrolled"] is True
    assert context["feature_count"] == 1
    assert node["feature"] == "Value"
    assert node["is_effect"] is True
    assert step.main_columns == []
    assert step.row_count == 1
