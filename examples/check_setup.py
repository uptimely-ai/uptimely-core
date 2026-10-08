"""Check that the environment can run the examples."""

import importlib.util
import sys
from pathlib import Path

REQUIRED_MODULES = ("polars", "pydantic", "graphable", "uptimely")
REPOSITORY_ROOT = Path(__file__).parent.parent


def main() -> None:
    """Validate Python, dependencies, and the example specification files."""
    problems: list[str] = []
    if sys.version_info < (3, 13):  # noqa: UP036 - intentional runtime guard for setup checks
        problems.append("Python 3.13 or newer is required")

    missing_modules = [
        module for module in REQUIRED_MODULES if importlib.util.find_spec(module) is None
    ]
    if missing_modules:
        problems.append(f"Missing dependencies: {', '.join(missing_modules)}")

    expected_files = (
        REPOSITORY_ROOT / "examples" / "example_1" / "generated" / "spec" / "spec.json",
        REPOSITORY_ROOT / "examples" / "example_2" / "spec" / "spec.py",
    )
    missing_files = [str(path) for path in expected_files if not path.exists()]
    if missing_files:
        problems.append(f"Missing example files: {', '.join(missing_files)}")

    if problems:
        raise SystemExit("Setup check failed:\n- " + "\n- ".join(problems))

    print("Setup looks good: Python, dependencies, and example specifications are ready.")


if __name__ == "__main__":
    main()
