import subprocess
import sys

import uptimely
import uptimely.compiler as compiler
import uptimely.engine as engine
import uptimely.spec as spec
from uptimely.compiler import plan
from uptimely.compiler.callable_node import CallableNode as CallableNodeImplementation
from uptimely.compiler.compiler import Compiler as CompilerImplementation
from uptimely.compiler.execution_graph import CallableGraph as CallableGraphImplementation
from uptimely.compiler.plan.models import ExecutionPlan, Plan
from uptimely.engine.config import EngineConfig
from uptimely.engine.engine import Engine as EngineImplementation
from uptimely.explorer import graph_render
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
        "uptimely.compiler.entrypoint",
        "uptimely.spec.explorer_render",
        "uptimely.spec.graph_render",
        "uptimely.spec.feature_graph.render",
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
    assert graph_render.GraphStyle.__module__ == "uptimely.explorer.graph_render"
    assert not hasattr(spec, "GraphStyle")
    assert not hasattr(feature_graph, "GraphStyle")
    assert feature_graph_models.FeatureNode is FeatureNode
    assert feature_graph_models.FunctionNode is FunctionNode
    assert uptimely.PythonSpec is spec.PythonSpec
    assert uptimely.SubGraph is spec.SubGraph is SubGraph

    assert uptimely.CallableGraph is compiler.CallableGraph is CallableGraphImplementation
    assert uptimely.CallableNode is compiler.CallableNode is CallableNodeImplementation
    assert uptimely.Compiler is compiler.Compiler is CompilerImplementation
    assert uptimely.ExecutionPlan is compiler.ExecutionPlan is ExecutionPlan
    assert uptimely.Engine is engine.Engine is EngineImplementation
    assert engine.EngineConfig is EngineConfig

    assert plan.Plan is Plan
    assert plan.ExecutionPlan is ExecutionPlan
