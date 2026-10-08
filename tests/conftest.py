"""Shared test setup: make example modules importable from the repository root."""

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).parent.parent
EXAMPLE_SPEC_DIRS = [
    REPOSITORY_ROOT / "examples" / "example_1" / "spec",
    REPOSITORY_ROOT / "examples" / "example_2" / "spec",
]

for path in [str(REPOSITORY_ROOT), *(str(directory) for directory in EXAMPLE_SPEC_DIRS)]:
    if path not in sys.path:
        sys.path.insert(0, path)
