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
from uptimely.spec.feature_graph.models import ActionNode, FeatureNode
from uptimely.spec.model import Spec as SpecModel


def test_canonical_package_exports_preserve_object_identity() -> None:
    assert spec.Spec is SpecModel
    assert uptimely.load_spec is spec.load_spec
    assert uptimely.from_python is spec.from_python
    assert uptimely.write_document is spec.write_document
    assert uptimely.Dimension is python_spec.Dimension
    assert uptimely.Entity is python_spec.Entity
    assert uptimely.FeatureGraph is spec.FeatureGraph is FeatureGraph
    assert feature_graph.FeatureGraphBase is FeatureGraphBase
    assert feature_graph.FeatureGraphNodeMeta is FeatureGraphNodeMeta
    assert graph_style.GraphStyle.__module__ == "uptimely.explorer.graph_style"
    assert feature_graph_models.FeatureNode is FeatureNode
    assert feature_graph_models.ActionNode is ActionNode
    assert uptimely.FeatureSubGraph is spec.FeatureSubGraph is FeatureSubGraph

    assert uptimely.InvocationGraph is compiler.InvocationGraph is InvocationGraphImplementation
    assert uptimely.InvocationNode is compiler.InvocationNode is InvocationNodeImplementation
    assert uptimely.Compiler is compiler.Compiler is CompilerImplementation
    assert uptimely.ExecutionPlan is execution_plan.ExecutionPlan is ExecutionPlan
    assert execution_plan.Invocation is Invocation
    assert uptimely.Engine is engine.Engine is EngineImplementation
    assert engine.EngineConfig is EngineConfig
    assert engine.ParameterConfig is ParameterConfig
    assert engine.Config is Config
    assert engine.Params is Params


def test_root_authoring_exports_preserve_object_identity() -> None:
    assert uptimely.Spec is python_spec.Spec
    assert uptimely.Action is python_spec.Action
    assert uptimely.Dataset is python_spec.Dataset
    assert uptimely.Feature is python_spec.Feature
    assert uptimely.Order is python_spec.Order
    assert uptimely.RowScope is python_spec.RowScope
    assert uptimely.function is python_spec.function
    assert uptimely.ref is python_spec.ref
