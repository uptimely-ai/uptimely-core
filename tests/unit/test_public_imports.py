import subprocess
import sys

import uptimely
import uptimely.analytics as analytics
import uptimely.compiler as compiler
import uptimely.engine as engine
from uptimely.analytics import feature_graph
from uptimely.analytics.feature_graph import FeatureGraph, SubGraph
from uptimely.analytics.feature_graph import models as feature_graph_models
from uptimely.analytics.feature_graph.models import FeatureNode, FunctionNode
from uptimely.analytics.model import Analytics as AnalyticsModel
from uptimely.compiler import plan
from uptimely.compiler.callable_node import CallableNode as CallableNodeImplementation
from uptimely.compiler.compiler import Compiler as CompilerImplementation
from uptimely.compiler.execution_graph import CallableGraph as CallableGraphImplementation
from uptimely.compiler.plan.models import ExecutionPlan, Plan
from uptimely.engine.config import EngineConfig
from uptimely.engine.engine import Engine as EngineImplementation
from uptimely.explorer import graph_render


def test_removed_compatibility_paths_are_unavailable_in_fresh_process() -> None:
    removed_paths = [
        "uptimely.compile",
        "uptimely.compile.compiler",
        "uptimely.compile.entrypoint",
        "uptimely.compile.execution_graph",
        "uptimely.compile.node",
        "uptimely.compile.render",
        "uptimely.compiler.entrypoint",
        "uptimely.analytics.explorer_render",
        "uptimely.analytics.graph_render",
        "uptimely.analytics.feature_graph.render",
        "uptimely.analytics.models",
        "uptimely.analytics.storage",
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
    assert uptimely.Analytics is analytics.Analytics is AnalyticsModel
    assert uptimely.load_analytics is analytics.load_analytics
    assert uptimely.from_python is analytics.from_python
    assert uptimely.prepare_analytics is analytics.prepare_analytics
    assert uptimely.write_document is analytics.write_document
    assert uptimely.PreparedAnalytics is analytics.PreparedAnalytics
    assert not hasattr(analytics, "AnalyticsParser")
    assert not hasattr(analytics, "AnalyticsSerializer")
    assert uptimely.Call is analytics.Call
    assert uptimely.Dimension is analytics.Dimension
    assert uptimely.Entity is analytics.Entity
    assert uptimely.FeatureGraph is analytics.FeatureGraph is FeatureGraph
    assert graph_render.GraphStyle.__module__ == "uptimely.explorer.graph_render"
    assert not hasattr(analytics, "GraphStyle")
    assert not hasattr(feature_graph, "GraphStyle")
    assert feature_graph_models.FeatureNode is FeatureNode
    assert feature_graph_models.FunctionNode is FunctionNode
    assert uptimely.Function is analytics.Function
    assert uptimely.PythonAnalytics is analytics.PythonAnalytics
    assert uptimely.SubGraph is analytics.SubGraph is SubGraph

    assert uptimely.CallableGraph is compiler.CallableGraph is CallableGraphImplementation
    assert uptimely.CallableNode is compiler.CallableNode is CallableNodeImplementation
    assert uptimely.Compiler is compiler.Compiler is CompilerImplementation
    assert uptimely.ExecutionPlan is compiler.ExecutionPlan is ExecutionPlan
    assert uptimely.Engine is engine.Engine is EngineImplementation
    assert engine.EngineConfig is EngineConfig

    assert plan.Plan is Plan
    assert plan.ExecutionPlan is ExecutionPlan
