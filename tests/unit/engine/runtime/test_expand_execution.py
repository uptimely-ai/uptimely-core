import polars as pl
import pytest
from support import execution as execution_support

from uptimely import compiler, spec
from uptimely.spec.python import assembly, dimension, feature, merge, profile, ref


def read_values(lazy: bool = False, empty: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame(
        {
            "group": ["A", "A", "B", "B"],
            "id": [1, 2, 3, 4],
            "value": [2, 4, 6, None],
        }
    )
    if empty:
        frame = frame.clear()
    return frame.lazy() if lazy else frame


def read_reference_constant(lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"source_value": [10.0]})
    return frame.lazy() if lazy else frame


def read_group_limits(lazy: bool = False) -> pl.DataFrame | pl.LazyFrame:
    frame = pl.DataFrame({"group": ["A", "B"], "source_value": [5.0, 7.0]})
    return frame.lazy() if lazy else frame


def broadcast_reference(
    source: pl.DataFrame | pl.LazyFrame, feature: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    return source.select(pl.col(feature).alias(output))


def broadcast_group_limit(
    source: pl.DataFrame | pl.LazyFrame, feature: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    return source.select("group", pl.col(feature).alias(output))


def inflate_reference(
    source: pl.DataFrame | pl.LazyFrame, feature: str, output: str
) -> pl.DataFrame | pl.LazyFrame:
    fragment = source.select(pl.col(feature).alias(output))
    if isinstance(fragment, pl.LazyFrame):
        fragment = fragment.collect()
    return pl.concat([fragment, fragment])


def _broadcast_spec(
    reader: object, expand_function: object, source_dimension_ids: list[str], lazy: bool
) -> spec.Spec:
    """Build a two-profile spec expanding a lower-dimensional source feature."""
    group = dimension.Dimension(
        id="group",
        resolutions=[dimension.Resolution(id="group", key="group", type="string")],
    )
    identifier = dimension.Dimension(
        id="id",
        resolutions=[dimension.Resolution(id="id", key="id", type="integer")],
    )
    dimensions = {"group": group, "id": identifier}
    observations = profile.Profile(
        id="observations",
        grain=[group.resolution("group"), identifier.resolution("id")],
        assembly=[
            assembly.Operator(
                id="read_values",
                inputs=[],
                outputs=[feature.Feature(id="value")],
                compute=assembly.Bind(
                    ref.function(read_values),
                    lazy=lazy,
                ),
                merge=merge.default(),
            ),
            assembly.Operator(
                id="reference",
                inputs=[ref.feature("source_value")],
                outputs=[feature.Feature(id="reference")],
                compute=assembly.Bind(
                    ref.function(expand_function),
                    source=ref.profile("reference_source").dataset,
                    feature=ref.feature("source_value").id,
                    output=ref.feature("reference").id,
                ),
                merge=merge.default(),
            ),
        ],
    )
    source = profile.Profile(
        id="reference_source",
        grain=[dimensions[name].resolution(name) for name in source_dimension_ids],
        assembly=[
            assembly.Operator(
                id="read_reference",
                inputs=[],
                outputs=[feature.Feature(id="source_value")],
                compute=assembly.Bind(
                    ref.function(reader),
                    lazy=lazy,
                ),
                merge=merge.default(),
            )
        ],
    )
    return spec.from_python(profiles=[observations, source])


@pytest.mark.parametrize("lazy", [False, True])
def test_expand_broadcasts_dimensionless_fragment(
    lazy, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _broadcast_spec(read_reference_constant, broadcast_reference, [], lazy)
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run()

    assert not result.failures
    frame = result.datasets["observations"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("id").to_dicts() == [
        {"group": "A", "id": 1, "value": 2, "reference": 10.0},
        {"group": "A", "id": 2, "value": 4, "reference": 10.0},
        {"group": "B", "id": 3, "value": 6, "reference": 10.0},
        {"group": "B", "id": 4, "value": None, "reference": 10.0},
    ]


@pytest.mark.parametrize("lazy", [False, True])
def test_expand_left_joins_fragment_on_its_carried_dimension_keys(
    lazy, engine_for_plan: execution_support.EngineFactory
):
    spec_definition = _broadcast_spec(read_group_limits, broadcast_group_limit, ["group"], lazy)
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run()

    assert not result.failures
    frame = result.datasets["observations"]
    if isinstance(frame, pl.LazyFrame):
        frame = frame.collect()
    assert frame.sort("id").select("group", "id", "reference").rows() == [
        ("A", 1, 5.0),
        ("A", 2, 5.0),
        ("B", 3, 7.0),
        ("B", 4, 7.0),
    ]


def test_fragment_dimension_policy_is_compiled_from_profile_relationship(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    spec_definition = _broadcast_spec(read_group_limits, broadcast_group_limit, ["group"], False)
    plan = compiler.Compiler().compile(spec_definition)
    assert (
        next(
            item for item in plan.invocations if item.operator_id == "reference"
        ).fragment_dimensions
        == "subset"
    )

    result = engine_for_plan(plan, spec_definition=spec_definition).run(validate=True)

    assert not result.failures
    assert result.datasets["observations"].sort("id").select("group", "id").rows() == [
        ("A", 1),
        ("A", 2),
        ("B", 3),
        ("B", 4),
    ]


def test_expand_rejects_multirow_dimensionless_fragment(
    engine_for_plan: execution_support.EngineFactory,
):
    spec_definition = _broadcast_spec(read_reference_constant, inflate_reference, [], False)
    plan = compiler.Compiler().compile(spec_definition)
    result = engine_for_plan(plan, spec_definition=spec_definition).run(validate=True)

    assert "at most one row" in next(iter(result.failures.values()))
