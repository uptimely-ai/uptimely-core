from uptimely.explorer import render
from uptimely.spec import model
from uptimely.spec.feature_graph import models


def test_render_field_filter_preserves_falsy_values() -> None:
    assert render.filled_fields(
        absent=None, flag=False, count=0, text="", items=[], metadata={}
    ) == {"flag": False, "count": 0, "text": "", "items": [], "metadata": {}}


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

    assert node.to_render_data() == {
        "node_type": "function",
        "is_function": True,
        "label": "double",
        "features": ["doubled"],
        "entity": "asset",
        "function_kind": "vectorize",
        "type": "python_function",
        "entrypoint": "example:double",
        "info": {"description": "Double a reading"},
    }
