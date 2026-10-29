from uptimely.explorer import render
from uptimely.explorer.common import serialize_graph_payload
from uptimely.explorer.sections import feature_lineage
from uptimely.spec import model
from uptimely.spec.feature_graph import models


def test_render_field_filter_preserves_falsy_values() -> None:
    assert render.filled_fields(
        absent=None, flag=False, count=0, text="", items=[], metadata={}
    ) == {"flag": False, "count": 0, "text": "", "items": [], "metadata": {}}


def test_graph_payload_serialization_is_stable_and_script_safe() -> None:
    payload = serialize_graph_payload(
        nodes=[{"id": "z", "label": "</script>"}, {"id": "a", "label": "first"}],
        links=[{"source": "z", "target": "z"}, {"source": "a", "target": "z"}],
    )

    assert payload == (
        r'{"nodes": [{"id": "a", "label": "first"}, {"id": "z", "label": "<\/script>"}], '
        '"links": [{"source": "a", "target": "z"}, {"source": "z", "target": "z"}]}'
    )


def test_feature_render_data_preserves_empty_strings() -> None:
    node = models.FeatureNode(name="reading", data_type="", entity="asset", dataset_id="telemetry")

    assert feature_lineage._node_render_data(node) == {
        "node_type": "feature",
        "is_action": False,
        "label": "reading",
        "entity": "asset",
        "dataset_id": "telemetry",
        "data_type": "",
    }


def test_action_render_data_includes_declared_function_metadata() -> None:
    function = model.FunctionTemplate(
        id="double",
        kind="vectorize",
        returns="dataframe",
        description="Double a reading",
        entrypoint="example:double",
    )
    node = models.ActionNode(
        action_id="double_action",
        features=("doubled",),
        entity="asset",
        dataset_id="telemetry",
        function=function,
    )

    assert feature_lineage._node_render_data(node) == {
        "node_type": "feature",
        "is_action": True,
        "label": "double",
        "action_id": "double_action",
        "features": ["doubled"],
        "entity": "asset",
        "dataset_id": "telemetry",
        "function_id": "double",
        "function_kind": "vectorize",
        "type": "python_function",
        "entrypoint": "example:double",
        "info": {"description": "Double a reading"},
    }
