"""Python authoring declarations for spec."""

from . import merge, ref
from .assembly import Binding, Operator
from .dimension import Dimension, Resolution
from .feature import Feature, FeatureSet
from .functions import function
from .merge import default_merge
from .profile import Order, Profile, ProfileRegistry
from .references import Params
from .spec import Spec

__all__ = [
    "Operator",
    "Binding",
    "Profile",
    "Dimension",
    "Resolution",
    "Feature",
    "FeatureSet",
    "ProfileRegistry",
    "Order",
    "Spec",
    "Params",
    "function",
    "default_merge",
    "merge",
    "ref",
]
