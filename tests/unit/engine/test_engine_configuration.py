import collections.abc
import copy
import pathlib
import types

import polars as pl
import pytest
from support import execution as execution_support

from uptimely import application as application_module
from uptimely import engine as uptimely_engine
from uptimely import plan as uptimely_plan
from uptimely import spec
from uptimely.codebase.python import entrypoint as entrypoint_module
from uptimely.engine.dataframe import fragment as fragment_module
from uptimely.engine.runtime import bindings as bindings_module
from uptimely.engine.runtime import execution as execution_module
from uptimely.engine.runtime import state as state_module
from uptimely.library.merge import polars as merge_module

PLAN_PATH = pathlib.Path(__file__).parents[2] / "fixtures" / "plans" / "simple_engine.json"


def _plan() -> uptimely_plan.ExecutionPlan:
    return uptimely_plan.from_json(PLAN_PATH)


def _patch_callables(monkeypatch: pytest.MonkeyPatch, callables: dict[str, object]) -> None:
    def merge_by_grain_entrypoint(
        dataset: merge_module.DataFrame | None,
        fragment: merge_module.DataFrame,
        dataset_identifiers: collections.abc.Sequence[str],
        fragment_keys: collections.abc.Sequence[str] | None = None,
        *,
        key_columns: collections.abc.Sequence[str] = (),
        join_cardinality: str = "m:m",
        broadcast_cardinality: str = "m:m",
    ) -> merge_module.DataFrame:
        return merge_module.merge_by_grain(
            dataset,
            fragment,
            dataset_identifiers,
            fragment_keys,
            key_columns=key_columns,
            join_cardinality=join_cardinality,
            broadcast_cardinality=broadcast_cardinality,
        )

    callables = {
        "uptimely.library.merge.polars:merge_by_grain": merge_by_grain_entrypoint,
        **callables,
    }

    class _TestEntrypoint:
        def __init__(
            self, location: str, package: entrypoint_module.PackageOrigin | None = None
        ) -> None:
            self.location = location
            self.package = package
            self.module = types.SimpleNamespace(location=location.split(":", 1)[0])

        @property
        def function(self) -> object:
            return self

        def load(self) -> object:
            return callables[self.location]

    monkeypatch.setattr(entrypoint_module, "Entrypoint", _TestEntrypoint)


def test_engine_validates_plan_backend(engine_for_plan: execution_support.EngineFactory) -> None:
    plan = _plan()

    with pytest.raises(ValueError, match="Unsupported plan backend"):
        engine_for_plan(copy.replace(plan, required_backend="pandas"))


@pytest.mark.parametrize("validate", [False, True])
def test_engine_execution_uses_only_saved_invocation_metadata(
    monkeypatch: pytest.MonkeyPatch,
    bundle_for_plan: execution_support.BundleFactory,
    validate: bool,
) -> None:
    raw = pl.DataFrame({"asset_id": ["A"], "reading": [2], "extra": [0]})

    def double(column: str, dataset: pl.DataFrame) -> pl.DataFrame:
        assert dataset.columns == ["asset_id", "reading"]
        return dataset.with_columns((pl.col(column) * 2).alias("doubled"))

    _patch_callables(
        monkeypatch,
        {
            "test:read": lambda **_: raw,
            "test:double": double,
            "test:write": lambda **_: None,
        },
    )
    bundle = bundle_for_plan(_plan())
    restored = uptimely_plan.from_dict(uptimely_plan.to_dict(bundle.execution_plan))
    bundle = copy.replace(bundle, execution_plan=restored, spec_definition=spec.Spec())
    engine = uptimely_engine.Engine(
        bundle, uptimely_engine.EngineConfig(), {"source": "input.json"}
    )

    result = engine.run(validate=validate)

    assert not result.failures
    assert result.datasets["telemetry"].to_dicts() == [
        {"asset_id": "A", "reading": 2, "doubled": 4}
    ]


def test_engine_selects_dataframe_backend_from_config(
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    engine = uptimely_engine.Engine(
        bundle_for_plan(_plan()),
        uptimely_engine.EngineConfig(backend={"dataframe": "POLARS"}),
    )

    assert isinstance(engine.backend, uptimely_engine.PolarsBackend)


def test_engine_uses_default_config_when_omitted(
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    engine = uptimely_engine.Engine(bundle_for_plan(_plan()))

    assert engine.config == uptimely_engine.EngineConfig()
    assert isinstance(engine.backend, uptimely_engine.PolarsBackend)


def test_engine_does_not_load_project_config_from_root_toml(
    bundle_for_plan: execution_support.BundleFactory,
) -> None:
    bundle = bundle_for_plan(_plan())
    (bundle.project_root / application_module.CONFIG_FILE).write_text(
        '[engine.backend]\ndataframe = "polars"\n\n[paths]\nsource = "data/input.csv"\n\n'
        "[params]\nthreshold = 10\n",
        encoding="utf-8",
    )

    engine = uptimely_engine.Engine(bundle)

    assert engine.paths == {}
    assert engine.parameters == {}


def test_engine_rejects_spec_paths_instead_of_compiling() -> None:
    with pytest.raises(ValueError, match="bundle must be a BuildBundle"):
        uptimely_engine.Engine("spec.json", uptimely_engine.EngineConfig())  # type: ignore[arg-type]


def test_engine_rejects_execution_plan_instead_of_bundle() -> None:
    with pytest.raises(ValueError, match="bundle must be a BuildBundle"):
        uptimely_engine.Engine(
            _plan(),
            uptimely_engine.EngineConfig(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("reference", ["$params.", "$params.source.path"])
def test_engine_rejects_malformed_parameter_references(
    reference: str, engine_for_plan: execution_support.EngineFactory
) -> None:
    engine = engine_for_plan(_plan())
    bindings = bindings_module.RuntimeBindings(state_module.RuntimeState(), engine.parameters)

    with pytest.raises(ValueError, match="Malformed parameter reference"):
        bindings.resolve_parameter_reference(reference)


def test_engine_rejects_ambiguous_fragment_references() -> None:
    first = execution_support.dataset(None)
    second = execution_support.dataset(None)
    first.fragments["shared"] = fragment_module.Fragment(pl.DataFrame({"asset_id": ["A"]}), ())
    second.fragments["shared"] = fragment_module.Fragment(pl.DataFrame({"asset_id": ["B"]}), ())
    state = state_module.RuntimeState(datasets={"first": first, "second": second})

    with pytest.raises(ValueError, match="Ambiguous fragment reference: shared"):
        state.resolve_dataset_or_fragment_dataframe("shared")


def test_fragment_names_are_scoped_by_profile(
    monkeypatch: pytest.MonkeyPatch, engine_for_plan: execution_support.EngineFactory
) -> None:
    def read(source: str) -> pl.DataFrame:
        return pl.DataFrame({"asset_id": [source], "reading": [1]})

    _patch_callables(monkeypatch, {"test:read": read})
    engine = engine_for_plan(_plan(), {"source": "source"})
    state = state_module.RuntimeState()
    executor = execution_module.InvocationExecutor(
        engine.backend,
        {},
        engine.parameters,
        state,
    )
    for profile_id in ("first", "second"):
        read = copy.replace(
            next(item for item in engine.plan.invocations if item.result == "fragment"),
            profile_id=profile_id,
            operator_id="shared",
        )
        merge = copy.replace(
            next(item for item in engine.plan.invocations if item.role == "merge"),
            id=f"invocation:merge:merge_by_grain:{profile_id}:shared",
            profile_id=profile_id,
            operator_id="shared",
            arguments={
                "dataset": profile_id,
                **{
                    key: value
                    for key, value in next(
                        item for item in engine.plan.invocations if item.role == "merge"
                    ).arguments.items()
                    if key != "dataset"
                },
            },
            dependency_ids=[read.id],
        )
        executor.execute(read)
        executor.execute(merge)

    assert set(state.datasets) == {"first", "second"}
    assert all(set(main.fragments) == {"shared"} for main in state.datasets.values())
    with pytest.raises(ValueError, match="Ambiguous fragment reference: shared"):
        state.resolve_dataset_or_fragment_dataframe("shared")
