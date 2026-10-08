"""Export example 1's Python specification to its JSON manifest."""

from pathlib import Path

from uptimely.spec import Specification

from .spec.spec import dimensions, entities

OUTPUT_PATH = Path(__file__).parent / "generated" / "spec" / "spec.json"


def main() -> None:
    """Build the Python specification and export it as JSON."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    specification = Specification.from_python(
        entities=entities,
        dimensions=dimensions,
    )
    output_path = specification.to_json(OUTPUT_PATH)
    print(f"Specification written to {output_path}")


if __name__ == "__main__":
    main()
