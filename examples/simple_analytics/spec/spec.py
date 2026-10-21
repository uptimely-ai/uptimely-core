"""Dataset declarations for simple analytics."""

from uptimely.spec.python import (
    PythonSpec,
    bind,
    dataset,
    dimension,
    entity,
    feature,
    mapping,
    ref,
)

from ..functions import functions

id_dimension = dimension.Dimension(
    id="id",
    type="integer",
    description="Stable identifier for each input row",
)
dimensions = [id_dimension]

features = [
    feature.Feature(id="input_1", description="Input feature: input_1"),
    feature.Feature(id="input_2", description="Input feature: input_2"),
    feature.Feature(id="id", type="integer", description="Stable identifier for each input row"),
    feature.Feature(id="column_3", description="Vectorized feature: column_3"),
    feature.Feature(id="column_4", description="Vectorized feature: column_4"),
]

mappings = [
    mapping.Mapping(
        id="read",
        bind=bind.bind(ref.function(functions.read_data, operation="read"), function_id="read"),
        outputs=[
            ref.feature("input_1"),
            ref.feature("input_2"),
            ref.feature("id"),
        ],
    ),
    mapping.Mapping(
        id="column_3",
        bind=bind.bind(
            ref.function(functions.sum_features, operation="vectorize"),
            left_feature=ref.feature("input_1"),
            right_feature=ref.feature("input_2"),
            output=ref.feature("column_3"),
            dataset=ref.current_dataset().dataframe,
        ),
        inputs=[ref.feature("input_1"), ref.feature("input_2")],
        outputs=[ref.feature("column_3")],
    ),
    mapping.Mapping(
        id="column_4",
        bind=bind.bind(
            ref.function(functions.tag_first_item, operation="vectorize"),
            function_id="column_4",
            output=ref.feature("column_4"),
            id_column=ref.dimension("id"),
            dataset=ref.current_dataset().dataframe,
        ),
        inputs=[ref.feature("id")],
        outputs=[ref.feature("column_4")],
    ),
    mapping.Mapping(
        inputs=[ref.feature("column_3"), ref.feature("column_4")],
        bind=bind.bind(
            ref.function(functions.write_data, operation="write"),
            function_id="write",
            df=ref.current_dataset(),
            cols=[ref.feature("column_3"), ref.feature("column_4")],
        ),
        id="write",
    ),
]

dataset_ = dataset.Dataset(
    id="my_beautiful_dataset",
    description="Dataset loaded by read.",
    row_scope=dataset.RowScope(
        grain="One row per id",
    ),
    features=features,
    mappings=mappings,
)

entity_ = entity.Entity(
    id="simple_analytics",
    name="Simple analytics",
    dimensions=[id_dimension],
    datasets=[dataset_],
    description="Simple analytics entity.",
)

python_spec = PythonSpec(
    entities=[entity_],
    dimensions=dimensions,
    name="Simple analytics",
)
