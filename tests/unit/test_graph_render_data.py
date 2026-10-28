from uptimely.explorer import render
from uptimely.explorer.common import serialize_graph_payload
from uptimely.explorer.sections import feature_graph
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
    node = models.FeatureNode(name="reading", data_type="", entity="asset")

    assert feature_graph._node_render_data(node) == {
        "node_type": "feature",
        "is_function": False,
        "label": "reading",
        "entity": "asset",
        "data_type": "",
    }


def test_function_render_data_includes_declared_metadata() -> None:
    function = model.FunctionTemplate(
        id="double",
        kind="vectorize",
        returns="dataframe",
        description="Double a reading",
        entrypoint="example:double",
    )
    node = models.FunctionNode(
        name="double", features=("doubled",), entity="asset", function=function
    )

    assert feature_graph._node_render_data(node) == {
        "node_type": "feature",
        "is_function": True,
        "label": "double",
        "features": ["doubled"],
        "entity": "asset",
        "function_kind": "vectorize",
        "type": "python_function",
        "entrypoint": "example:double",
        "info": {"description": "Double a reading"},
    }
