"""Entry point for the Uptimely command-line interface."""

import argparse

from uptimely.cli import docs, engine, examples, plan, spec

download_examples = examples.download_examples
build_docs = docs.build_docs
serve_docs = docs.serve_docs


def main() -> None:
    """Run the Uptimely command-line interface."""
    parser = argparse.ArgumentParser(prog="uptimely")
    commands = parser.add_subparsers(dest="command", required=True)
    examples.configure_parser(commands.add_parser("examples", help="Manage example projects"))
    docs.configure_parser(
        commands.add_parser(
            "explorer", help="Explore analytics specifications, lineage, and execution plans"
        )
    )
    spec.configure_parser(
        commands.add_parser("spec", help="Export and inspect analytics specifications")
    )
    plan.configure_parser(commands.add_parser("plan", help="Build execution plans"))
    engine.configure_parser(commands.add_parser("engine", help="Run analytics workflows"))
    args = parser.parse_args()
    if args.command == "examples":
        examples.run(args, parser)
    elif args.command == "explorer":
        docs.run(args, parser)
    elif args.command == "spec":
        spec.run(args, parser)
    elif args.command == "plan":
        plan.run(args, parser)
    else:
        engine.run(args, parser)


if __name__ == "__main__":
    main()
