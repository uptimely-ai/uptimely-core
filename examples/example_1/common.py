import sys
from pathlib import Path

from uptimely.spec import Specification

EXAMPLE_DIR = Path(__file__).parent
SPEC_PATH = EXAMPLE_DIR / "generated" / "spec" / "spec.json"
GENERATED_DIR = EXAMPLE_DIR / "generated"


def load_specification() -> Specification:
    """Load the example specification from its JSON manifest."""
    return Specification.from_json(SPEC_PATH)


def verbose_requested() -> bool:
    """Return whether a runner was asked to print diagnostic details."""
    return "--verbose" in sys.argv[1:]
