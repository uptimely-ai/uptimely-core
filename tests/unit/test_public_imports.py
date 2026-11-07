import uptimely
import uptimely.compiler as compiler
import uptimely.engine as engine
import uptimely.execution_plan as legacy_execution_plan
import uptimely.plan as execution_plan
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
from uptimely.explorer import graph_style
from uptimely.plan.models import ExecutionPlan, Invocation
from uptimely.spec import feature_graph
from uptimely.spec import model as spec_model
from uptimely.spec import python as python_spec
from uptimely.spec.feature_graph import (
    FeatureGraph,
    FeatureGraphBase,
    FeatureGraphNodeMeta,
    FeatureSubGraph,
)
from uptimely.spec.feature_graph import models as feature_graph_models
from uptimely.spec.feature_graph.models import FeatureNode, OperatorNode
from uptimely.spec.model import Profile as ProfileModel
from uptimely.spec.model import Spec as SpecModel
from uptimely.spec.model import (
    base,
    binding,
    binding_argument,
    dimension,
    functions,
)
from uptimely.spec.model import spec as document


def test_canonical_package_exports_preserve_object_identity() -> None:
    assert spec.Spec is SpecModel
    assert spec.Profile is ProfileModel
    assert spec.model.Profile is ProfileModel
    assert not hasattr(spec.model, "Dataset")
    assert not hasattr(spec.model, "BindingArgumentResolver")
    assert uptimely.load_spec is spec.load_spec
    assert uptimely.from_python is spec.from_python
    assert uptimely.write_document is spec.write_document
    assert uptimely.Dimension is python_spec.Dimension
    assert not hasattr(spec, "Options")
    assert not hasattr(python_spec, "Options")
    assert not hasattr(uptimely, "Entity")
    assert not hasattr(python_spec, "Entity")
    assert uptimely.FeatureGraph is spec.FeatureGraph is FeatureGraph
    assert feature_graph.FeatureGraphBase is FeatureGraphBase
    assert feature_graph.FeatureGraphNodeMeta is FeatureGraphNodeMeta
    assert graph_style.GraphStyle.__module__ == "uptimely.explorer.graph_style"
    assert feature_graph_models.FeatureNode is FeatureNode
    assert feature_graph_models.OperatorNode is OperatorNode
    assert uptimely.FeatureSubGraph is spec.FeatureSubGraph is FeatureSubGraph

    assert uptimely.InvocationGraph is compiler.InvocationGraph is InvocationGraphImplementation
    assert uptimely.InvocationNode is compiler.InvocationNode is InvocationNodeImplementation
    assert uptimely.Compiler is compiler.Compiler is CompilerImplementation
    assert uptimely.ExecutionPlan is execution_plan.ExecutionPlan is ExecutionPlan
    assert execution_plan.Invocation is Invocation
    assert legacy_execution_plan.ExecutionPlan is execution_plan.ExecutionPlan
    assert legacy_execution_plan.Invocation is execution_plan.Invocation
    assert uptimely.Engine is engine.Engine is EngineImplementation
    assert engine.EngineConfig is EngineConfig
    assert engine.ParameterConfig is ParameterConfig
    assert engine.Config is Config
    assert engine.Params is Params


def test_root_authoring_exports_preserve_object_identity() -> None:
    assert uptimely.Spec is python_spec.Spec
    assert uptimely.Operator is python_spec.Operator
    assert not hasattr(uptimely, "Action")
    assert not hasattr(python_spec, "Action")
    assert uptimely.Profile is python_spec.Profile
    assert not hasattr(uptimely, "Dataset")
    assert not hasattr(python_spec, "Dataset")
    assert not hasattr(python_spec, "DatasetRegistry")
    assert python_spec.ProfileRegistry is python_spec.profile.ProfileRegistry
    assert uptimely.Feature is python_spec.Feature
    assert uptimely.Order is python_spec.Order
    assert not hasattr(uptimely, "RowScope")
    assert not hasattr(python_spec, "RowScope")
    assert uptimely.function is python_spec.function
    assert uptimely.ref is python_spec.ref


def test_document_models_are_exported_from_focused_modules() -> None:
    assert spec_model.StrictModel is base.StrictModel
    assert spec_model.Binding is binding.Binding
    assert spec_model.BindingArgument is binding_argument.BindingArgument
    assert not hasattr(binding_argument, "BindingArgumentResolver")
    assert spec_model.Dimension is dimension.Dimension
    assert spec_model.Resolution is dimension.Resolution
    assert spec_model.Argument is functions.Argument
    assert spec_model.SpecSource is document.SpecSource
    assert not hasattr(spec_model, "common")
