from uptimely import analytics, compiler, render
from uptimely.analytics.feature_graph import models


def test_render_field_filter_preserves_falsy_values() -> None:
    assert render.filled_fields(
        absent=None, flag=False, count=0, text="", items=[], metadata={}
    ) == {"flag": False, "count": 0, "text": "", "items": [], "metadata": {}}


def test_callable_render_data_preserves_empty_values_and_omits_none() -> None:
    node = compiler.CallableNode(function_id="load", entity="asset", operation="read")

    assert node.to_render_data() == {
        "node_type": "callable",
        "operation": "read",
        "label": "load(asset)",
        "function_id": "load",
        "entity": "asset",
        "output_features": [],
    }


def test_feature_render_data_preserves_empty_strings() -> None:
    node = models.FeatureNode(name="reading", data_type="", entity="asset")

    assert node.to_render_data("feature") == {
        "node_type": "feature",
        "is_function": False,
        "label": "reading",
        "entity": "asset",
        "data_type": "",
    }


def test_function_render_data_includes_declared_metadata() -> None:
    function = analytics.Function(
        id="double",
        type="python_function",
        role="analytics",
        info={"description": "Double a reading"},
        entrypoint="example:double",
    )
    node = models.FunctionNode(
        name="double", features=("doubled",), entity="asset", function=function
    )

    assert node.to_render_data() == {
        "node_type": "function",
        "is_function": True,
        "label": "double",
        "features": ["doubled"],
        "entity": "asset",
        "function_type": "vectorize",
        "type": "python_function",
        "entrypoint": "example:double",
        "info": {"description": "Double a reading"},
    }
