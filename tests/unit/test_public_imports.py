import subprocess
import sys

import uptimely
import uptimely.compiler as compiler
import uptimely.engine as engine
import uptimely.execution_plan as execution_plan
import uptimely.spec as spec
import uptimely.spec.model as spec_model
from uptimely.compiler.compiler import Compiler as CompilerImplementation
from uptimely.compiler.graph import (
    InvocationGraph as InvocationGraphImplementation,
)
from uptimely.compiler.graph import (
    InvocationNode as InvocationNodeImplementation,
)
from uptimely.engine.config import Config, EngineConfig, ParameterConfig, Params
from uptimely.engine.engine import Engine as EngineImplementation
from uptimely.execution_plan.models import ExecutionPlan, Invocation
from uptimely.explorer import graph_style
from uptimely.spec import feature_graph
from uptimely.spec import python as python_spec
from uptimely.spec.feature_graph import (
    FeatureGraph,
    FeatureGraphBase,
    FeatureGraphNodeMeta,
    FeatureSubGraph,
)
from uptimely.spec.feature_graph import models as feature_graph_models
from uptimely.spec.feature_graph.models import FeatureNode, FunctionNode
from uptimely.spec.model import Spec as SpecModel
from uptimely.spec.python import row_context as authoring_context


def test_removed_compatibility_paths_are_unavailable_in_fresh_process() -> None:
    removed_paths = [
        "uptimely.compile",
        "uptimely.compile.compiler",
        "uptimely.compile.entrypoint",
        "uptimely.compile.execution_graph",
        "uptimely.compile.node",
        "uptimely.compile.render",
        "uptimely.contracts",
        "uptimely.compiler.entrypoint",
        "uptimely.compiler.plan",
        "uptimely.compiler.plan.models",
        "uptimely.compiler.plan.serialization",
        "uptimely.compiler.callable_node",
        "uptimely.compiler.execution_graph",
        "uptimely.spec.explorer_render",
        "uptimely.spec.feature_graph_render",
        "uptimely.spec.graph",
        "uptimely.spec.feature_graph.graph",
        "uptimely.explorer.graph_render",
        "uptimely.explorer.sections.lineage",
        "uptimely.explorer.sections.plan_graph",
        "uptimely.explorer.lineage",
        "uptimely.explorer.plan_render",
        "uptimely.explorer.spec_render",
        "uptimely.spec.models",
        "uptimely.spec.storage",
        "uptimely.plan",
        "uptimely.plan.models",
        "uptimely.plan.serialization",
        "uptimely.project.paths",
    ]
    script = f"""
import importlib
for name in {removed_paths!r}:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError:
        continue
    raise AssertionError(f"Removed compatibility path still imports: {{name}}")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_canonical_package_exports_preserve_object_identity() -> None:
    assert spec.Spec is SpecModel
    assert uptimely.load_spec is spec.load_spec
    assert uptimely.from_python is spec.from_python
    assert uptimely.write_document is spec.write_document
    assert not hasattr(spec, "SpecParser")
    assert not hasattr(spec, "SpecSerializer")
    assert uptimely.Dimension is python_spec.Dimension
    assert uptimely.Entity is python_spec.Entity
    assert uptimely.FeatureGraph is spec.FeatureGraph is FeatureGraph
    assert feature_graph.FeatureGraphBase is FeatureGraphBase
    assert feature_graph.FeatureGraphNodeMeta is FeatureGraphNodeMeta
    assert graph_style.GraphStyle.__module__ == "uptimely.explorer.graph_style"
    assert not hasattr(spec, "GraphStyle")
    assert not hasattr(feature_graph, "GraphStyle")
    assert feature_graph_models.FeatureNode is FeatureNode
    assert feature_graph_models.FunctionNode is FunctionNode
    assert uptimely.FeatureSubGraph is spec.FeatureSubGraph is FeatureSubGraph

    assert uptimely.InvocationGraph is compiler.InvocationGraph is InvocationGraphImplementation
    assert uptimely.InvocationNode is compiler.InvocationNode is InvocationNodeImplementation
    assert uptimely.Compiler is compiler.Compiler is CompilerImplementation
    assert uptimely.ExecutionPlan is ExecutionPlan
    assert execution_plan.Invocation is Invocation
    assert not hasattr(execution_plan, "Callable")
    assert uptimely.Engine is engine.Engine is EngineImplementation
    assert engine.EngineConfig is EngineConfig
    assert engine.ParameterConfig is ParameterConfig
    assert engine.Config is Config
    assert engine.Params is Params

    assert execution_plan.ExecutionPlan is ExecutionPlan


def test_root_authoring_exports_preserve_object_identity() -> None:
    assert uptimely.Spec is python_spec.Spec
    assert uptimely.Action is python_spec.Action
    assert uptimely.Dataset is python_spec.Dataset
    assert uptimely.Feature is python_spec.Feature
    assert uptimely.Order is python_spec.Order
    assert uptimely.RowScope is python_spec.RowScope
    assert uptimely.function is python_spec.function
    assert uptimely.ref is python_spec.ref


def test_obsolete_exports_are_unavailable() -> None:
    removed_exports = [
        (uptimely, ["PythonSpec"]),
        (python_spec, ["PythonSpec"]),
        (
            spec,
            [
                "PythonSpec",
                "RowContext",
                "actions",
                "bind",
                "dataset",
                "dimension",
                "entity",
                "feature",
                "ref",
                "row_context",
            ],
        ),
        (compiler, ["ExecutionPlan"]),
        (spec_model, ["FUNCTION_TYPES", "FUNCTION_KINDS"]),
        (authoring_context, ["RowContext", "ContextExtent", "UNBOUNDED"]),
    ]
    for module, names in removed_exports:
        for name in names:
            assert not hasattr(module, name), f"{module.__name__}.{name}"
            assert name not in module.__all__
