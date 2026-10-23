"""Declarative dataset definition for simple analytics."""

from examples.simple_analytics.functions import functions
from uptimely.spec.python import Dataset, Feature, FunctionMapping, RowScope, ref

from .. import entity


class SimpleAnalytics(Dataset):
    """Input values and two derived features at identifier grain."""

    id = "my_beautiful_dataset"
    description = "Dataset loaded by read."
    entity = entity.SIMPLE_ANALYTICS
    row_scope = RowScope(grain="One row per id")

    read = FunctionMapping(
        function=functions.read_data,
        function_id="read",
        arguments={},
        outputs=[
            Feature(name="input_1", description="Input feature: input_1"),
            Feature(name="input_2", description="Input feature: input_2"),
        ],
    )

    column_3 = FunctionMapping(
        function=functions.sum_features,
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            left_feature=ref.feature("input_1"),
            right_feature=ref.feature("input_2"),
            output=ref.feature("column_3").id,
        ),
        outputs=[Feature(name="column_3", description="Vectorized feature: column_3")],
    )

    column_4 = FunctionMapping(
        function=functions.tag_first_item,
        function_id="column_4",
        arguments=dict(  # noqa: C408
            dataset=ref.current_dataset().dataframe,
            output=ref.feature("column_4").id,
            id_column=ref.dimension("id"),
        ),
        inputs=[ref.feature("id")],
        outputs=[Feature(name="column_4", description="Vectorized feature: column_4")],
    )

    write = FunctionMapping(
        function=functions.write_data,
        function_id="write",
        arguments=dict(  # noqa: C408
            df=ref.current_dataset(), cols=[ref.feature("column_3"), ref.feature("column_4")]
        ),
        outputs=[],
    )
