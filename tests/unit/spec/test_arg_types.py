from uptimely.spec import arg_types


def test_atomic_argument_types_are_declared_in_one_place() -> None:
    assert arg_types.ATOMIC_ARGUMENT_TYPES == (
        arg_types.DATAFRAME,
        arg_types.STRING,
        arg_types.INTEGER,
        arg_types.FLOAT,
        arg_types.BOOLEAN,
        arg_types.ARRAY,
        arg_types.OBJECT,
    )


def test_collection_type_helpers_compose_and_extract_nested_types() -> None:
    expression = arg_types.object_values_of(arg_types.array_of(arg_types.DATAFRAME))

    assert expression == "object{str: array[dataframe]}"
    assert arg_types.object_value_type(expression) == "array[dataframe]"
    assert arg_types.array_item_type("array[dataframe]") == arg_types.DATAFRAME
    assert arg_types.array_item_type("array") is None
    assert arg_types.object_value_type("object") is None
