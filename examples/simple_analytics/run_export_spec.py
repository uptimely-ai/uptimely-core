from pathlib import Path

from uptimely.spec import Specification

from .spec.spec import python_specification

OUTPUT_PATH = Path(__file__).parent / "_generated" / "spec" / "spec.json"


def main() -> None:
    """Build the Python specification and export it as JSON."""
    specification = Specification.from_python(
        entities=python_specification.entities,
        dimensions=python_specification.dimensions,
        name=python_specification.name,
    )
    output_path = specification.to_json(OUTPUT_PATH)
    print(f"Specification written to {output_path}")


if __name__ == "__main__":
    main()
