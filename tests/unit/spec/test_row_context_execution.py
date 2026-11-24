import datetime
import json
import pathlib

import polars as pl
from support import execution as execution_support

from uptimely import compiler, spec
from uptimely import plan as uptimely_plan
from uptimely.explorer import presentation
from uptimely.spec.python import assembly, dimension, feature, merge, profile, ref
from uptimely.spec.python import row_context as authoring


def read_observations() -> pl.DataFrame:
    return pl.DataFrame(
        {
            "timestamp": [datetime.datetime(2026, 1, 2), datetime.datetime(2026, 1, 1)],
            "temperature": [10, 20],
        }
    )


def calculate(dataset: pl.DataFrame, column: str, output: str, configuration: dict) -> pl.DataFrame:
    assert configuration == {"windows": ["8h", "24h"]}
    return dataset.with_columns((pl.col(column) + 1).alias(output))


def maximum(dataset: pl.DataFrame, column: str, output: str) -> pl.DataFrame:
    """Return a whole-dataset maximum without observation-context requirements."""
    return dataset.select(pl.col(column).max().alias(output))


def _spec(context=None, *, ordered=True, dimension_type="datetime"):
    timestamp = dimension.Dimension(
        id="timestamp",
        resolutions=[
            dimension.Resolution(
                id="timestamp",
                key="timestamp",
                type=dimension_type,
            )
        ],
    )
    return spec.from_python(
        profiles=[
            profile.Profile(
                id="observations",
                grain=[timestamp.at("timestamp")],
                order=[profile.Order(timestamp, "timestamp", "asc")] if ordered else [],
                assembly=[
                    assembly.Operator(
                        id="read_observations",
                        inputs=[],
                        outputs=[
                            feature.Feature(id="temperature", type="integer"),
                        ],
                        compute=assembly.Bind(
                            ref.function(read_observations),
                        ),
                    ),
                    assembly.Operator(
                        id="result",
                        inputs=[ref.input("temperature")],
                        outputs=[feature.Feature(id="result", type="integer")],
                        compute=assembly.Bind(
                            ref.function(calculate),
                            dataset=ref.profile().dataset,
                            column=ref.input("temperature").id,
                            output=ref.output("result").id,
                            configuration={"windows": ["8h", "24h"]},
                        ),
                        row_context=context,
                    ),
                ],
            )
        ]
    )


def test_spec_plan_execution_and_presentation_preserve_context(
    tmp_path: pathlib.Path, engine_for_plan: execution_support.EngineFactory
) -> None:
    context = authoring.time(
        "24h", dimension=ref.dimension("timestamp"), before="24h", after="2h"
    ).row_context
    spec_definition = _spec(context)
    path = tmp_path / "spec.json"
    spec.write_document(spec_definition, path)
    payload = json.loads(path.read_text())
    authored_profile = payload["profiles"]["observations"]
    assert "row_context" not in authored_profile["features"]["result"]
    assert authored_profile["assembly"]["result"]["row_context"] == context.to_dict()
    restored = spec.load_spec(path)
    compiled = compiler.Compiler().compile(restored)
    invocation = next(
        item for item in compiled.invocations if item.semantics.row_context is not None
    )
    assert invocation.semantics.input_features == ["temperature"]
    assert invocation.semantics.row_context == context
    portable = uptimely_plan.from_dict(uptimely_plan.to_dict(compiled))
    result = engine_for_plan(portable, spec_definition=restored).run()
    assert not result.failures
    frame = result.datasets["observations"]
    assert frame.sort("timestamp")["result"].to_list() == [21, 11]
    data = presentation.build_presentation_data(restored, compiled)
    rendered_invocation = next(
        step
        for stage in data["stages"]
        for step in stage["steps"]
        if step["function"] == "calculate"
    )
    assert rendered_invocation["row_context"] == context.to_dict()


def test_operator_preserves_annotated_context():
    declaration = assembly.Operator(
        id="declaration",
        inputs=[],
        outputs=[],
        compute=assembly.Bind(
            ref.function(f"{__name__}:calculate", returns="dataframe"),
            configuration={"windows": [authoring.rows(8, before=7)]},
        ),
    )
    assert declaration.to_model().row_context.before.rows == 7
    assert declaration.to_model().compute.model_dump()["args"] == {
        "configuration": {"windows": [8]}
    }


def test_spec_plan_and_batch_execution_preserve_context_and_arguments(
    tmp_path: pathlib.Path,
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    context = authoring.time("8h", dimension=ref.dimension("timestamp"), before="8h").row_context
    spec_definition = _spec(context)
    spec_path = tmp_path / "spec.json"
    spec.write_document(spec_definition, spec_path)
    restored_spec = spec.load_spec(spec_path)
    original_operator = spec_definition.profiles["observations"].assembly["result"]
    restored_operator = restored_spec.profiles["observations"].assembly["result"]
    assert restored_operator.row_context == original_operator.row_context == context
    assert (
        "row_context"
        not in spec_definition.profiles["observations"].assembly["result"].compute.model_dump()
    )
    exported = json.loads(spec_path.read_text())
    exported_profile = exported["profiles"]["observations"]
    exported_feature = exported_profile["features"]["result"]
    assert "row_context" not in exported_feature
    assert exported_profile["assembly"]["result"]["row_context"] == context.to_dict()
    assert "compute" not in exported_feature
    assert (
        "row_context" not in exported["profiles"]["observations"]["assembly"]["result"]["compute"]
    )
    assert spec_definition.functions["calculate"].args["column"].type == "string"

    plan = compiler.Compiler().compile(restored_spec)
    invocation = next(item for item in plan.invocations if item.semantics.row_context is not None)
    source = next(
        item for item in plan.invocations if item.semantics.operator_id == "read_observations"
    )
    assert invocation.semantics.row_context == context
    assert all(
        item.semantics.row_context is None for item in plan.invocations if item is not invocation
    )
    assert invocation.arguments == {
        "dataset": source.returns,
        "column": "temperature",
        "output": "result",
        "configuration": {"windows": ["8h", "24h"]},
    }
    assert spec_definition.profiles["observations"].order == [
        spec.Order(dimension="timestamp", resolution="timestamp", direction="asc")
    ]
    plan_path = uptimely_plan.export_json(plan, tmp_path / "plan.json")
    restored_plan = uptimely_plan.from_json(plan_path)
    assert restored_plan == plan
    result = engine_for_plan(restored_plan, spec_definition=restored_spec).run()
    assert not result.failures
    frame = next(iter(result.datasets.values()))
    assert frame["result"].to_list() == [11, 21]
    assert frame["timestamp"].to_list() == [
        datetime.datetime(2026, 1, 2),
        datetime.datetime(2026, 1, 1),
    ]

    data = presentation.build_presentation_data(restored_spec, restored_plan)
    step = next(
        step
        for stage in data["stages"]
        for step in stage["steps"]
        if step["function"] == "calculate"
    )
    assert step["row_context"] == context.to_dict()


def test_plan_context_is_present_in_portable_operations() -> None:
    plan = compiler.Compiler().compile(_spec(context=authoring.current()))
    invocation = next(
        item for item in plan.invocations if "result" in item.semantics.output_features
    )
    assert invocation.semantics.row_context == authoring.current()


def test_collapse_functions_execute_without_row_context(
    engine_for_plan: execution_support.EngineFactory,
) -> None:
    source = profile.Profile(
        id="observations",
        assembly=[
            assembly.Operator(
                id="read_observations",
                inputs=[],
                outputs=[
                    feature.Feature(id="temperature", type="integer"),
                ],
                compute=assembly.Bind(
                    ref.function(read_observations),
                ),
            )
        ],
    )
    summary = profile.Profile(
        id="summary",
        assembly=[
            assembly.Operator(
                id="summary",
                inputs=[ref.input("temperature")],
                outputs=[feature.Feature(id="temperature_max", type="integer")],
                compute=assembly.Bind(
                    ref.function(maximum),
                    dataset=ref.profile("observations").dataset,
                    column=ref.input("temperature").id,
                    output=ref.output("temperature_max").id,
                ),
                merge=merge.default(),
            )
        ],
    )
    timestamp = dimension.Dimension(
        id="timestamp",
        resolutions=[dimension.Resolution(id="timestamp", key="timestamp", type="datetime")],
    )
    spec_definition = spec.from_python(
        profiles=[
            profile.Profile(
                id=source.id,
                grain=[timestamp.at("timestamp")],
                assembly=source.assembly,
            ),
            profile.Profile(
                id=summary.id,
                assembly=summary.assembly,
            ),
        ]
    )
    plan = compiler.Compiler().compile(spec_definition)
    invocation = next(item for item in plan.invocations if item.entrypoint.endswith(":maximum"))
    source_invocation = next(
        item
        for item in plan.invocations
        if item.semantics.profile_id == "observations"
        and item.semantics.operator_id == "read_observations"
    )
    assert invocation.semantics.row_context is None
    assert invocation.entrypoint.endswith(":maximum")
    assert invocation.arguments == {
        "dataset": source_invocation.returns,
        "column": "temperature",
        "output": "temperature_max",
    }
    output_profile = spec_definition.profiles["summary"]
    output = output_profile.assembly["summary"]
    assert output.row_context is None
    payload = output.model_dump()
    assert "group_by" not in payload
    assert "row_context" not in payload["compute"]
    restored = uptimely_plan.from_dict(json.loads(json.dumps(uptimely_plan.to_dict(plan))))
    assert restored == plan
    result = engine_for_plan(restored, spec_definition=spec_definition).run()
    assert not result.failures
    assert result.datasets["summary"]["temperature_max"].to_list() == [20]
