import subprocess
import sys

import uptimely
import uptimely.compiler as compiler
import uptimely.engine as engine
import uptimely.execution_plan as execution_plan
import uptimely.spec as spec
from uptimely.compiler.compiler import Compiler as CompilerImplementation
from uptimely.compiler.graph import (
    InvocationGraph as InvocationGraphImplementation,
)
from uptimely.compiler.graph import (
    InvocationNode as InvocationNodeImplementation,
)
from uptimely.engine.config import EngineConfig
from uptimely.engine.engine import Engine as EngineImplementation
from uptimely.execution_plan.models import ExecutionPlan, Invocation
from uptimely.explorer import graph_style
from uptimely.spec import feature_graph
from uptimely.spec.feature_graph import FeatureGraph, SubGraph
from uptimely.spec.feature_graph import models as feature_graph_models
from uptimely.spec.feature_graph.models import FeatureNode, FunctionNode
from uptimely.spec.model import Spec as SpecModel


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
        "uptimely.spec.graph_render",
        "uptimely.spec.feature_graph.render",
        "uptimely.explorer.graph_render",
        "uptimely.explorer.lineage",
        "uptimely.explorer.plan_render",
        "uptimely.explorer.spec_render",
        "uptimely.spec.models",
        "uptimely.spec.storage",
        "uptimely.plan",
        "uptimely.plan.models",
        "uptimely.plan.serialization",
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
    assert uptimely.Spec is spec.Spec is SpecModel
    assert uptimely.load_spec is spec.load_spec
    assert uptimely.from_python is spec.from_python
    assert uptimely.write_document is spec.write_document
    assert not hasattr(spec, "SpecParser")
    assert not hasattr(spec, "SpecSerializer")
    assert uptimely.Dimension is spec.Dimension
    assert uptimely.Entity is spec.Entity
    assert uptimely.FeatureGraph is spec.FeatureGraph is FeatureGraph
    assert graph_style.GraphStyle.__module__ == "uptimely.explorer.graph_style"
    assert not hasattr(spec, "GraphStyle")
    assert not hasattr(feature_graph, "GraphStyle")
    assert feature_graph_models.FeatureNode is FeatureNode
    assert feature_graph_models.FunctionNode is FunctionNode
    assert uptimely.PythonSpec is spec.PythonSpec
    assert uptimely.SubGraph is spec.SubGraph is SubGraph

    assert uptimely.InvocationGraph is compiler.InvocationGraph is InvocationGraphImplementation
    assert uptimely.InvocationNode is compiler.InvocationNode is InvocationNodeImplementation
    assert uptimely.Compiler is compiler.Compiler is CompilerImplementation
    assert uptimely.ExecutionPlan is compiler.ExecutionPlan is ExecutionPlan
    assert execution_plan.Invocation is Invocation
    assert not hasattr(execution_plan, "Callable")
    assert uptimely.Engine is engine.Engine is EngineImplementation
    assert engine.EngineConfig is EngineConfig

    assert execution_plan.ExecutionPlan is ExecutionPlan
