"""Dataset declarations for example 2."""

from uptimely.spec.python_spec import bind, dataset, dimension, entity, feature, fragment, ref

from ..functions import functions

dimensions = [
    dimension.Dimension(
        id="id",
        type="integer",
        description="Stable identifier for each input row",
    ),
]

calculations = [
    feature.Vectorize(
        id="column_3",
        description="Vectorized feature: column_3",
        bind=bind.bind(
            functions.sum_features,
            left_feature=ref.feature("input_1"),
            right_feature=ref.feature("input_2"),
            output=ref.feature("column_3"),
        ),
    ),
    feature.Vectorize(
        id="column_4",
        description="Vectorized feature: column_4",
        bind=bind.bind(
            functions.tag_first_item,
            function_id="column_4",
            output=ref.feature("column_4"),
            id_column=ref.dimension("id"),
        ),
    ),
]

read_fragment = fragment.Read(
    id="read",
    bind=bind.bind(functions.read_data, function_id="read"),
    features=[
        feature.Raw(id="input_1", description="Input feature: input_1"),
        feature.Raw(id="input_2", description="Input feature: input_2"),
        feature.Raw(id="id", description="Stable identifier for each input row"),
    ],
)

write_fragment = fragment.Write(
    bind=bind.bind(
        functions.write_data,
        function_id="write",
        df=ref.current_dataset(),
        cols=[ref.feature("column_3"), ref.feature("column_4")],
    ),
    id="write",
)

dataset_ = dataset.Dataset(
    id="my_beautiful_dataset",
    description="Dataset loaded by read.",
    row_scope=dataset.RowScope(
        grain="One row per id",
    ),
    read=[read_fragment],
    vectorize=calculations,
    write=[write_fragment],
)

entity_ = entity.Entity(
    id="example_2",
    name="Example 2",
    dimensions=["id"],
    datasets=[dataset_],
    description="Example 2 entity.",
)
