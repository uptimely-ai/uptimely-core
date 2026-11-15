"""Public package namespace for uptimely."""

# Load spec before the compiler to initialize the declaration and document models.
from .spec import (  # noqa: I001
    FeatureGraph,
    FeatureSubGraph,
    from_python,
    load_spec,
    write_document,
)
from .spec.python import (
    Operator,
    Binding,
    Profile,
    Dimension,
    Feature,
    FeatureSet,
    Order,
    Params,
    Resolution,
    Spec,
    function,
    default_merge,
    merge,
    ref,
)
from .compiler import Compiler, InvocationGraph, InvocationNode
from .plan.models import ExecutionPlan
from .engine import Engine
from .application import Uptimely

__all__ = [
    "Spec",
    "Params",
    "Operator",
    "Binding",
    "Profile",
    "Feature",
    "FeatureSet",
    "Order",
    "function",
    "default_merge",
    "merge",
    "ref",
    "Compiler",
    "Dimension",
    "Resolution",
    "ExecutionPlan",
    "from_python",
    "load_spec",
    "write_document",
    "FeatureSubGraph",
    "FeatureGraph",
    "Engine",
    "Uptimely",
    "InvocationGraph",
    "InvocationNode",
]
